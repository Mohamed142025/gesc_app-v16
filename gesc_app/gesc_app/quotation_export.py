"""A quotation downloaded as Word or Excel in the layout of one of its print formats.

Both start from the print format's own rendered HTML, so they follow the template and the
print permissions (an unapproved draft is refused exactly as when printed):

- Word: the HTML with its styles inlined and its images embedded, as a single-file web page
  (.doc) that Word opens with the same tables, colours, header and footer.
- Excel: the GESC quotation layout read from that HTML (its info table, project, items with
  their titles, totals, terms, signatures and attachments) and laid out on a sheet. A print
  format without that layout is written table by table.
"""

import base64
import io
import mimetypes
import re
from urllib.parse import unquote

import frappe
from frappe import _
from frappe.utils import cint, flt

BLUE = "1F4E8C"
LIGHT = "DBE5F1"
GREY = "F2F2F2"
GREEN = "C6E0B4"
OPTION_BAR = "D9D9D9"
# A proposal's colour (quotation_options), by its row class o1..o5.
OPTION_FILLS = {"o1": "E2EFDA", "o2": "DAE3F3", "o3": "FBE5D6", "o4": "FFF2CC", "o5": "EDEDED"}
FONT = "Arial"
IMAGE_EXT = ("jpg", "jpeg", "png", "gif", "bmp")


@frappe.whitelist()
def download(name, print_format=None, file_type="word"):
	from frappe.www.printview import get_rendered_template

	doc = frappe.get_doc("Quotation", name)
	print_format = print_format or frappe.get_meta("Quotation").default_print_format
	if not print_format or frappe.db.get_value("Print Format", print_format, "doc_type") != "Quotation":
		frappe.throw(_("اختر نموذج طباعة لعرض السعر."))
	pf = frappe.get_doc("Print Format", print_format)
	# Checks the print permission and runs before_print (unapproved drafts are refused).
	html = get_rendered_template(doc, print_format=pf, no_letterhead=1)

	filename = re.sub(r"[\\/:*?\"<>|]+", "-", f"{doc.name} - {print_format}")
	if file_type == "excel":
		frappe.response.filecontent = to_excel(html, doc)
		frappe.response.filename = f"{filename}.xlsx"
	else:
		frappe.response.filecontent = to_word(html, doc)
		frappe.response.filename = f"{filename}.doc"
	frappe.response.type = "download"
	frappe.response.display_content_as = "attachment"


# ---------------------------------------------------------------- shared


def _soup(html):
	from bs4 import BeautifulSoup

	return BeautifulSoup(html, "lxml")


def _image_bytes(src):
	"""The bytes and type of an image the template shows: a data URI or a site file."""
	if not src:
		return None, None
	if src.startswith("data:"):
		head, _sep, data = src.partition(",")
		mime = head[5:].split(";")[0] or "image/png"
		try:
			return base64.b64decode(data), mime
		except Exception:
			return None, None
	path = unquote(src.split("?")[0])
	path = re.sub(r"^https?://[^/]+", "", path)
	if not path.startswith(("/files/", "/private/files/")):
		return None, None
	name = frappe.db.get_value("File", {"file_url": path, "is_folder": 0})
	if not name:
		return None, None
	try:
		content = frappe.get_doc("File", name).get_content()
	except Exception:
		return None, None
	if isinstance(content, str):
		content = content.encode()
	return content, mimetypes.guess_type(path)[0] or "image/png"


def _fit(content, max_w, max_h):
	"""The size (px) that fits the image in the box, keeping its proportions."""
	from PIL import Image

	try:
		w, h = Image.open(io.BytesIO(content)).size
	except Exception:
		return max_w, max_h
	scale = min(max_w / w, max_h / h, 1)
	return max(int(w * scale), 1), max(int(h * scale), 1)


def _text(el):
	"""The text of an element with its lines kept (paragraphs, divs and <br>)."""
	if el is None:
		return ""
	for br in el.find_all("br"):
		br.replace_with("\n")
	for block in el.find_all(["p", "div", "li", "tr"]):
		block.insert_after("\n")
	text = el.get_text()
	lines = [re.sub(r"[ \t\xa0]+", " ", line).strip() for line in text.split("\n")]
	return "\n".join(line for line in lines if line)


def _number(text):
	text = (text or "").replace(",", "").strip()
	try:
		return float(text)
	except ValueError:
		return None


# ---------------------------------------------------------------- Word


def to_word(html, doc):
	from premailer import Premailer

	# The embedded web fonts are of no use to Word and only make the file heavy.
	html = re.sub(r"<style>\s*@font-face.*?</style>", "", html, flags=re.S)
	html = Premailer(
		f'<html><head><meta charset="utf-8"></head><body>{html}</body></html>',
		remove_classes=False,
		keep_style_tags=False,
		strip_important=True,
		disable_validation=True,
		disable_leftover_css=True,
		allow_network=False,
		cssutils_logging_level="CRITICAL",
	).transform()

	soup = _soup(html)
	for el in soup.find_all(style=True):
		style = el["style"].replace("GescCairo", "Cairo")
		style = re.sub(r"font-family\s*:[^;]*", "font-family: Cairo, Arial, sans-serif", style)
		el["style"] = style
	for el in soup.find_all(["table", "div", "p", "td"]):
		el["dir"] = "ltr" if "direction: ltr" in (el.get("style") or "") else "rtl"

	# Widths of the columns go on the cells, where Word reads them.
	for table in soup.find_all("table"):
		widths = []
		for col in table.find_all("col"):
			match = re.search(r"width\s*:\s*([\d.]+)%", col.get("style", ""))
			widths.append(flt(match.group(1)) if match else 0)
		for row in table.find_all("tr"):
			cells = row.find_all(["td", "th"], recursive=False)
			if not widths or sum(cint(c.get("colspan") or 1) for c in cells) != len(widths):
				continue
			start = 0
			for cell in cells:
				span = cint(cell.get("colspan") or 1)
				width = sum(widths[start : start + span])
				start += span
				if width:
					cell["width"] = f"{width:g}%"
		for colgroup in table.find_all("colgroup"):
			colgroup.decompose()
		table["width"] = "100%"
		table["cellspacing"] = "0"
		table["cellpadding"] = "4"

	# Page numbers as Word fields.
	for cls, code in (("page", "PAGE"), ("topage", "NUMPAGES")):
		for span in soup.find_all("span", class_=cls):
			span.string = "1"
			span["style"] = f"mso-field-code:' {code} '"

	# Images: embedded in the file, with an explicit size (Word ignores max-width/height).
	parts = []
	for i, img in enumerate(soup.find_all("img"), 1):
		content, mime = _image_bytes(img.get("src"))
		if not content:
			img.decompose()
			continue
		in_header = img.find_parent(id="header-html") is not None
		in_gallery = img.find_parent("table", class_="gq-gal") is not None
		single = img.find_parent("td", class_="one") is not None
		box = (200, 52) if in_header else ((640, 257) if single else (320, 257) if in_gallery else (640, 760))
		w, h = _fit(content, *box)
		ext = (mimetypes.guess_extension(mime) or ".png").lstrip(".")
		location = f"quotation_files/image{i:03d}.{ext}"
		img["src"] = location
		img["width"], img["height"] = str(w), str(h)
		img["style"] = f"width:{w}px;height:{h}px"
		parts.append((location, mime, content))

	header = soup.find(id="header-html")
	footer = soup.find(id="footer-html")
	for el, element_id, kind in ((header, "h1", "header"), (footer, "f1", "footer")):
		if el is not None:
			el.extract()
			el.attrs = {"style": f"mso-element:{kind}", "id": element_id}

	body = soup.body.decode_contents() if soup.body else str(soup)
	# Word takes a page's header and footer from elements kept off the page.
	hidden = ""
	if header is not None or footer is not None:
		hidden = (
			'<table style="margin-left:50in;mso-hide:all"><tr><td>'
			+ (str(header) if header is not None else "")
			+ (str(footer) if footer is not None else "")
			+ "</td></tr></table>"
		)
	page = f"""<html xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office"
xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40">
<head><meta charset="utf-8"><title>{frappe.utils.escape_html(doc.name)}</title>
<!--[if gte mso 9]><xml><w:WordDocument><w:View>Print</w:View><w:Zoom>100</w:Zoom></w:WordDocument></xml><![endif]-->
<style>
@page Section1 {{ size: 21cm 29.7cm; margin: 3.2cm 0.9cm 2.6cm 0.9cm; mso-header-margin: 0.6cm; mso-footer-margin: 0.6cm;
  mso-header: h1; mso-footer: f1; }}
div.Section1 {{ page: Section1; }}
body {{ font-family: Cairo, Arial, sans-serif; font-size: 10.5pt; }}
p {{ margin: 0; }}
table {{ border-collapse: collapse; mso-table-lspace: 0; mso-table-rspace: 0; }}
</style></head>
<body dir="rtl"><div class="Section1" dir="rtl">{body}</div>{hidden}</body></html>"""

	boundary = "----=_NextPart_GESC_Quotation"
	out = [
		"MIME-Version: 1.0",
		f'Content-Type: multipart/related; boundary="{boundary}"; type="text/html"',
		"",
		f"--{boundary}",
		"Content-Location: file:///C:/quotation.htm",
		"Content-Transfer-Encoding: base64",
		'Content-Type: text/html; charset="utf-8"',
		"",
		_b64_lines(page.encode()),
	]
	for location, mime, content in parts:
		out += [
			f"--{boundary}",
			f"Content-Location: file:///C:/{location}",
			"Content-Transfer-Encoding: base64",
			f"Content-Type: {mime}",
			"",
			_b64_lines(content),
		]
	out.append(f"--{boundary}--")
	return "\r\n".join(out).encode()


def _b64_lines(data):
	encoded = base64.b64encode(data).decode()
	return "\r\n".join(encoded[i : i + 76] for i in range(0, len(encoded), 76))


# ---------------------------------------------------------------- Excel


class _Sheet:
	"""Writes the quotation on a right-to-left sheet of six columns."""

	WIDTHS = (6, 58, 12, 10, 14, 17)

	def __init__(self, title):
		from openpyxl import Workbook

		self.wb = Workbook()
		self.ws = self.wb.active
		self.ws.title = title[:31]
		self.ws.sheet_view.rightToLeft = True
		self.ws.sheet_view.showGridLines = False
		for i, width in enumerate(self.WIDTHS, 1):
			self.ws.column_dimensions[self._col(i)].width = width
		self.row = 1
		ps = self.ws.page_setup
		ps.paperSize = self.ws.PAPERSIZE_A4
		ps.orientation = "portrait"
		ps.fitToWidth, ps.fitToHeight = 1, 0
		self.ws.sheet_properties.pageSetUpPr.fitToPage = True
		self.ws.print_options.horizontalCentered = True
		self.ws.page_margins.left = self.ws.page_margins.right = 0.4
		self.ws.page_margins.top, self.ws.page_margins.bottom = 0.5, 0.6

	@staticmethod
	def _col(i):
		from openpyxl.utils import get_column_letter

		return get_column_letter(i)

	def cell(self, col, value, *, span=1, bold=False, fill=None, size=10.5, align="center", wrap=True,
			 color="1D1D1B", border=True, number=None, row=None):
		from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

		row = row or self.row
		c = self.ws.cell(row=row, column=col, value=value)
		c.font = Font(name=FONT, bold=bold, size=size, color=color)
		c.alignment = Alignment(horizontal=align, vertical="center", wrap_text=wrap, readingOrder=2)
		if number:
			c.number_format = number
		side = Side(style="thin", color=BLUE)
		for i in range(col, col + span):
			target = self.ws.cell(row=row, column=i)
			if fill:
				target.fill = PatternFill("solid", fgColor=fill)
			if border:
				target.border = Border(left=side, right=side, top=side, bottom=side)
		if span > 1:
			self.ws.merge_cells(start_row=row, start_column=col, end_row=row, end_column=col + span - 1)
		return c

	def height(self, lines, per_line=15):
		self.ws.row_dimensions[self.row].height = max(lines, 1) * per_line + 4

	def image(self, content, col, max_w, max_h, row=None):
		from openpyxl.drawing.image import Image as XLImage

		w, h = _fit(content, max_w, max_h)
		img = XLImage(io.BytesIO(content))
		img.width, img.height = w, h
		self.ws.add_image(img, f"{self._col(col)}{row or self.row}")
		return h

	def save(self):
		out = io.BytesIO()
		self.wb.save(out)
		return out.getvalue()


def _lines(text, width):
	"""Roughly how many lines the text takes in a column `width` characters wide."""
	return sum(max(1, -(-len(line) // max(int(width * 1.15), 1))) for line in (text or "").split("\n")) or 1


def to_excel(html, doc):
	soup = _soup(html)
	sheet = _Sheet(doc.name)
	items_table = soup.find("table", class_="gq-items")
	if items_table is None:
		_generic_excel(soup, sheet)
		return sheet.save()

	ws = sheet.ws
	# Header: the logo and the company's name.
	head = soup.find(id="header-html")
	if head is not None:
		logo = head.find("img")
		content, _mime = _image_bytes(logo.get("src")) if logo else (None, None)
		ws.row_dimensions[sheet.row].height = 44
		ws.row_dimensions[sheet.row + 1].height = 4
		if content:
			sheet.image(content, 4, 190, 52)
		name = head.find(class_="gq-name")
		if name is not None:
			sub = name.find("span")
			sub_text = sub.extract().get_text(strip=True) if sub else ""
			sheet.cell(1, f"{name.get_text(strip=True)}\n{sub_text}".strip(), span=3, bold=True, size=15,
					   color=BLUE, fill=GREY, border=False, align="right")
			for col in range(4, 7):
				sheet.cell(col, None, fill=GREY, border=False)
		sheet.row += 2

	# The info table: three cells a row.
	info = soup.find("table", class_="gq-info")
	if info is not None:
		for tr in info.find_all("tr"):
			cells = tr.find_all("td")
			for (col, span), td in zip(((1, 2), (3, 2), (5, 2)), cells, strict=False):
				centre = "c" in (td.get("class") or [])
				sheet.cell(col, td.get_text(" ", strip=True), span=span, bold=True, align="center" if centre else "right")
			sheet.height(1, 18)
			sheet.row += 1
		ws.row_dimensions[sheet.row].height = 5
		sheet.cell(1, None, span=6, fill=BLUE, border=False)
		sheet.row += 1

	project = soup.find(class_="gq-project")
	if project is not None:
		sheet.cell(1, project.get_text(" ", strip=True), span=6, bold=True, size=11.5)
		sheet.height(1, 20)
		sheet.row += 2

	# Column titles.
	for col, th in enumerate(items_table.find_all("th")[:6], 1):
		sheet.cell(col, th.get_text(strip=True), bold=True, fill=GREY, size=11)
	sheet.height(1, 20)
	sheet.row += 1

	first_item_row = None
	for table in soup.find_all("table", class_="gq-items")[1:]:
		for tr in table.find_all("tr"):
			cells = tr.find_all("td")
			classes = tr.get("class") or []
			# An item's proposals share its number cell (rowspan): the rows after the first have five.
			if len(cells) == 5 and not ({"tot", "grand", "sec", "opt"} & set(classes)):
				cells = [None, *cells]
			option_fill = next((OPTION_FILLS[c] for c in classes if c in OPTION_FILLS), None)
			if "opt" in classes:
				sheet.cell(1, cells[0].get_text(" ", strip=True), span=6, bold=True, fill=OPTION_BAR, size=12.5)
				sheet.height(1, 21)
			elif "sec" in classes:
				sheet.cell(1, cells[0].get_text(" ", strip=True), span=6, bold=True, fill=LIGHT, size=11.5)
				sheet.height(1, 19)
			elif "tot" in classes or "grand" in classes:
				fill = option_fill or (GREEN if "grand" in classes else GREY)
				sheet.cell(1, cells[0].get_text(" ", strip=True), span=5, bold=True, fill=fill, size=12)
				value = _number(cells[-1].get_text())
				if value is not None and cells[0].get_text(strip=True) in ("الإجمالي", "الإجمالي قبل الخصم") and first_item_row:
					value = f"=SUM(F{first_item_row}:F{sheet.row - 1})"
				sheet.cell(6, value, bold=True, fill=fill, size=12, number="#,##0.00")
				sheet.height(1, 19)
			elif len(cells) == 6:
				first_item_row = first_item_row or sheet.row
				description = _text(cells[1])
				qty, rate = _number(cells[3].get_text()), _number(cells[4].get_text())
				fill = option_fill
				number = cells[0].get_text(strip=True) if cells[0] is not None else ""
				sheet.cell(1, cint(_number(number) or 0) or number or None, bold=True, fill=fill)
				sheet.cell(2, description, align="right", fill=fill)
				sheet.cell(3, cells[2].get_text(" ", strip=True), bold=True, size=10, fill=fill)
				sheet.cell(4, qty if qty is not None else cells[3].get_text(strip=True), bold=True, number="#,##0.##", fill=fill)
				sheet.cell(5, rate if rate is not None else cells[4].get_text(strip=True), bold=True, number="#,##0.##", fill=fill)
				amount = f"=D{sheet.row}*E{sheet.row}" if qty is not None and rate is not None else _number(cells[5].get_text())
				sheet.cell(6, amount, bold=True, number="#,##0.00", fill=fill)
				sheet.height(_lines(description, sheet.WIDTHS[1]))
			else:
				continue
			sheet.row += 1

	_excel_option_totals(soup, sheet)

	terms = soup.find(class_="gq-terms")
	if terms is not None:
		text = _text(terms)
		sheet.cell(1, text, span=6, bold=True, align="right")
		sheet.height(_lines(text, sum(sheet.WIDTHS)))
		sheet.row += 2

	sign = soup.find("table", class_="gq-sign")
	if sign is not None:
		cells = sign.find_all("td")
		spans = _spans(len(cells))
		for (col, span), td in zip(spans, cells, strict=False):
			name = td.find(class_="nm")
			name_text = name.extract().get_text(" ", strip=True) if name else ""
			sheet.cell(col, f"{td.get_text(' ', strip=True)}\n{name_text}".strip(), span=span, bold=True)
		sheet.height(2, 17)
		sheet.row += 2

	_excel_attachments(soup, sheet)

	foot = soup.find(id="footer-html")
	if foot is not None:
		sheet.row += 1
		for tr in foot.find_all("tr"):
			texts = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
			texts = [t for t in texts if t and "|" not in t]
			if texts:
				sheet.cell(1, "    —    ".join(texts), span=6, size=9, fill=GREY, border=False, color="333333")
				sheet.row += 1
		ws.oddFooter.center.text = f"{doc.name}  |  &P / &N"
		ws.oddFooter.center.size = 8
	return sheet.save()


def _excel_option_totals(soup, sheet):
	"""The proposals' totals (quotation_options): a line each, the proposal over two columns,
	then its totals (before the discount, the discount, after it) in its colour."""
	table = soup.find("table", class_="gq-cmp")
	if table is None:
		return
	sheet.row += 1
	for tr in table.find_all("tr"):
		cells = tr.find_all(["th", "td"])
		header = tr.find("th") is not None
		fill = GREY if header else next((OPTION_FILLS[c] for c in (tr.get("class") or []) if c in OPTION_FILLS), None)
		sheet.cell(1, cells[0].get_text(" ", strip=True), span=2, bold=True, fill=fill)
		for i, cell in enumerate(cells[1:]):
			value = cell.get_text(" ", strip=True) if header else _number(cell.get_text())
			after = "after" in (cell.get("class") or [])
			sheet.cell(3 + i, value, bold=True, fill=fill, size=12 if after else 10.5, number=None if header else "#,##0.00")
		sheet.height(2 if header else 1, 16)
		sheet.row += 1
	sheet.row += 1


def _spans(count):
	"""Split the six columns between `count` cells."""
	if not count:
		return []
	if count > 6:
		return [(i, 1) for i in range(1, 7)]
	base, extra = divmod(6, count)
	spans, col = [], 1
	for i in range(count):
		span = base + (1 if i < extra else 0)
		spans.append((col, span))
		col += span
	return spans


def _excel_attachments(soup, sheet):
	listing = soup.find("table", class_="gq-att-list")
	if listing is None:
		return
	title = soup.find(class_="gq-att-title")
	sheet.cell(1, title.get_text(" ", strip=True) if title else _("المرفقات"), span=6, bold=True, fill=LIGHT,
			   align="right", size=11.5)
	sheet.height(1, 19)
	sheet.row += 1
	for tr in listing.find_all("tr"):
		th = tr.find_all("th")
		if th:
			for (col, span), cell in zip(((1, 1), (2, 1), (3, 4)), th, strict=False):
				sheet.cell(col, cell.get_text(strip=True), span=span, bold=True, fill=GREY)
		else:
			td = tr.find_all("td")
			if len(td) < 3:
				continue
			sheet.cell(1, td[0].get_text(strip=True), bold=True)
			sheet.cell(2, _text(td[1]), align="right", bold=True)
			link = td[2].find("a")
			c = sheet.cell(3, td[2].get_text(" ", strip=True), span=4, align="right")
			if link is not None and link.get("href"):
				c.hyperlink = link["href"]
				from openpyxl.styles import Font

				c.font = Font(name=FONT, size=10.5, color=BLUE, underline="single")
		sheet.height(1, 18)
		sheet.row += 1

	# The images, two a row, each with its caption under it.
	images = []
	for td in soup.select("table.gq-gal td"):
		img = td.find("img")
		if img is None:
			continue
		content, _mime = _image_bytes(img.get("src"))
		caption = td.find(class_="cap")
		if content:
			images.append((content, caption.get_text(" ", strip=True) if caption else ""))
	sheet.row += 1
	for i in range(0, len(images), 2):
		pair = images[i : i + 2]
		top = sheet.row
		tallest = 0
		for (content, _caption), (col, box_w) in zip(pair, ((1, 440), (3, 370)), strict=False):
			tallest = max(tallest, sheet.image(content, col, box_w, 250, row=top))
		sheet.ws.row_dimensions[top].height = tallest * 0.75 + 6
		sheet.row += 1
		for (_content, caption), (col, span) in zip(pair, ((1, 2), (3, 4)), strict=False):
			sheet.cell(col, caption, span=span, bold=True, fill=LIGHT, size=10)
		sheet.height(1, 18)
		sheet.row += 2


def _generic_excel(soup, sheet):
	"""Any other print format: its tables, one sheet row per table row."""
	for table in soup.find_all("table"):
		if table.find_parent("table") is not None:
			continue
		for tr in table.find_all("tr"):
			cells = tr.find_all(["td", "th"], recursive=False)
			for col, td in enumerate(cells[:6], 1):
				text = _text(td)
				value = _number(text)
				sheet.cell(col, value if value is not None else text, bold=td.name == "th",
						   fill=GREY if td.name == "th" else None, align="right")
			sheet.row += 1
		sheet.row += 1
