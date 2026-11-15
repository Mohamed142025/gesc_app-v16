"""Item search that forgives Arabic spelling.

ERPNext's item search (erpnext.controllers.queries.item_query, used by the items tables of
quotations, orders, requests and the task's items) matches the text as typed. It is wrapped
here so that the spellings people mix up find the same items: أ/إ/آ/ا, ى/ي, ة/ه, ؤ/و, ئ/ي,
ذ/د, ث/ت, ظ/ض, the diacritics and the tatweel, Arabic or Latin digits, and the words in any
order ("ذهبي احمر" finds "أحمر دهبي"). ERPNext's own matches come first, as before; the items
it misses follow.
"""

import re

import frappe
from frappe.utils import strip_html

# Items scanned in Python: beyond this, the search is ERPNext's alone.
MAX_ITEMS = 20000
LOOSE_LIMIT = 10000

_CHARS = str.maketrans(
	{
		"أ": "ا",
		"إ": "ا",
		"آ": "ا",
		"ٱ": "ا",
		"ى": "ي",
		"ئ": "ي",
		"ؤ": "و",
		"ة": "ه",
		"ذ": "د",
		"ث": "ت",
		"ظ": "ض",
		"ـ": "",
		**{chr(0x0660 + i): str(i) for i in range(10)},
		**{chr(0x06F0 + i): str(i) for i in range(10)},
	}
)
_DIACRITICS = re.compile(r"[ً-ٰٟ]")


def normalize(text):
	text = _DIACRITICS.sub("", (text or "").lower())
	return re.sub(r"\s+", " ", text.translate(_CHARS)).strip()


def patch():
	try:
		from erpnext.controllers import queries
	except Exception:
		return
	if getattr(queries, "__gesc_item_search_patched__", False):
		return
	original = queries.item_query

	@frappe.whitelist()
	@frappe.validate_and_sanitize_search_inputs
	def item_query(doctype, txt, searchfield, start, page_len, filters, as_dict=False, **kwargs):
		return _item_query(original, doctype, txt, searchfield, start, page_len, filters, as_dict)

	item_query.__wrapped_item_query__ = original
	queries.item_query = item_query
	queries.__gesc_item_search_patched__ = True


def _item_query(original, doctype, txt, searchfield, start, page_len, filters, as_dict):
	words = normalize(txt).split()
	if not words or frappe.db.estimate_count("Item") > MAX_ITEMS:
		return original(doctype, txt, searchfield, start, page_len, filters, as_dict)
	start, page_len = int(start or 0), int(page_len or 20)

	# Every item the filters allow, in ERPNext's shape and order...
	allowed = original(doctype, "", searchfield, 0, LOOSE_LIMIT, _copy(filters), as_dict)
	# ...and the text each of them is searched in.
	haystack = {
		row.name: normalize(
			" ".join(
				strip_html(str(value or ""))
				for value in (row.name, row.item_name, row.item_group, row.description, row.get("customer_code"))
			)
		)
		for row in frappe.get_all(
			"Item",
			filters={"name": ("in", [_name(row) for row in allowed] or ["-"])},
			fields=["name", "item_name", "item_group", "description", *(_extra_fields())],
		)
	}
	phrase = " ".join(words)

	def score(row):
		text = haystack.get(_name(row), "")
		name = normalize(_name(row))
		return (0 if name.startswith(phrase) else 1, 0 if phrase in text else 1, text.find(words[0]))

	matches = [row for row in allowed if all(word in haystack.get(_name(row), "") for word in words)]
	matches.sort(key=score)

	# ERPNext's matches first, in its order, then the loose ones.
	full = original(doctype, txt, searchfield, 0, start + page_len, _copy(filters), as_dict)
	seen = {_name(row) for row in full}
	merged = list(full) + [row for row in matches if _name(row) not in seen]
	return merged[start : start + page_len]


def _name(row):
	return row.get("name") if isinstance(row, dict) else row[0]


def _copy(filters):
	import copy

	return copy.deepcopy(filters)


def _extra_fields():
	return ["customer_code"] if frappe.get_meta("Item").has_field("customer_code") else []
