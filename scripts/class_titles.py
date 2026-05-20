"""class_id (int) → human-readable shift title (str).

This is the only file you edit when you want to relabel a class on the homepage.
Empty strings are intentional placeholders; the sync script normalizes "" to
NULL in the database, and the frontend will fall back to "EMS-<id>".

Class 917 is intentionally absent — that class number is unused in the program.
"""

CLASS_TITLES: dict[int, str] = {
    912: "",
    913: "Adv. Patient Assessment",
    914: "",
    915: "",
    916: "",
    # 917 intentionally absent.
    918: "",
    919: "",
    920: "",
    921: "",
}
