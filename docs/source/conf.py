# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# http://www.sphinx-doc.org/en/master/config

# -- Path setup --------------------------------------------------------------

import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath("../../"))

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import monailabel

# -- Project information -----------------------------------------------------

project = "MONAI Label"
copyright = "2020 - 2021 MONAI Consortium"
author = "MONAI Label Contributors"

# The full version, including alpha/beta/rc tags
short_version = monailabel.__version__.split("+")[0]
release = short_version
version = short_version

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
# Add napoleon to the extensions list
# source_parsers = {'.md': CommonMarkParser}

templates_path = ["templates"]

source_suffix = {
    ".rst": "restructuredtext",
    ".txt": "restructuredtext",
    ".md": "markdown",
}

extensions = [
    "recommonmark",
    "sphinx.ext.intersphinx",
    "sphinx.ext.mathjax",
    "sphinx.ext.napoleon",
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.autosectionlabel",
    "sphinxcontrib.exceltable",
    "sphinx_autodoc_typehints",
]

autoclass_content = "both"
add_module_names = False
source_encoding = "utf-8"
autosectionlabel_prefix_document = True
napoleon_use_param = True
napoleon_include_init_with_doc = True
set_type_checking_flag = False

# Add any paths that contain templates here, relative to this directory.
# templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["endpoints", "tools", "static"]

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "pydata_sphinx_theme"
html_theme_options = {
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/project-monai/monailabel",
            "icon": "fab fa-github-square",
        },
        {
            "name": "Twitter",
            "url": "https://twitter.com/projectmonai",
            "icon": "fab fa-twitter-square",
        },
    ],
    "collapse_navigation": True,
    "navigation_depth": 3,
    "show_toc_level": 1,
    "footer_items": ["copyright"],
    "navbar_align": "content",
}
html_context = {
    "github_user": "Project-MONAI",
    "github_repo": "MONAILabel",
    "github_version": "main",
    "doc_path": "docs/",
    "conf_py_path": "/docs/",
    "VERSION": version,
}

html_scaled_image_link = False
html_show_sourcelink = True
html_favicon = "../images/favicon.ico"
html_logo = "../images/MONAI-logo-color.png"
html_sidebars = {"**": ["search-field", "sidebar-nav-bs"]}
pygments_style = "sphinx"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["../_static"]
html_css_files = ["custom.css"]
html_title = f"{project} {version} Documentation"


def generate_apidocs(*args):
    """Generate API docs automatically by trawling the available modules"""
    module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "monailabel"))
    output_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "apidocs"))
    apidoc_command_path = "sphinx-apidoc"
    if hasattr(sys, "real_prefix"):  # called from a virtualenv
        apidoc_command_path = os.path.join(sys.prefix, "bin", "sphinx-apidoc")
        apidoc_command_path = os.path.abspath(apidoc_command_path)
    print(f"output_path {output_path}")
    print(f"module_path {module_path}")
    subprocess.check_call(
        [apidoc_command_path, "-e"]
        + ["-o", output_path]
        + [module_path]
        + [os.path.join(module_path, p) for p in exclude_patterns]
    )


def setup(app):
    # Hook to allow for automatic generation of API docs
    # before doc deployment begins.
    app.connect("builder-inited", generate_apidocs)
