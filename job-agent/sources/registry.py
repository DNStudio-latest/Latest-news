import importlib

ALL = ["tripura_university", "nit_agartala", "nehu", "icfai_tripura", "techno_india_tripura", "sister_nivedita",
       "northeast_universities", "prasar_bharati", "pib", "tripura_ica", "nenow", "national_media",
       "naukri", "indeed", "linkedin", "mysarkarinaukri", "internshala", "upwork", "fiverr", "fellowships"]


def load(names=None):
    return [importlib.import_module(f"sources.{n}").SOURCE for n in (names or ALL)]
