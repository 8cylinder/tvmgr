from importlib.metadata import version as pkg_version

project = "tvmgr"
author = "Sheldon McGrandle"
release = pkg_version("tvmgr")

extensions = ["myst_parser", "sphinx_click"]
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}

root_doc = "index"
exclude_patterns = ["_build"]
html_theme = "furo"

man_pages = [
    (
        "cli",
        "tvmgr",
        "Manage TV shows and movies on Kodi media centers",
        ["Sheldon McGrandle"],
        1,
    ),
]
