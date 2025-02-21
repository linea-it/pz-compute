# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'PzCompute'
copyright = '2025, LIneA'
author = 'LIneA'
release = '0.0.1'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = []

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

language = 'pt'

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

extensions = ["sphinx.ext.napoleon", "sphinx.ext.mathjax", "sphinx.ext.viewcode"]

extensions.append("autoapi.extension")
extensions.append("nbsphinx")

templates_path = []
exclude_patterns = ["build", "**.ipynb_checkpoints", "html"]

master_doc = "index"  # This assumes that sphinx-build is called from the root directory
html_show_sourcelink = (
    False  # Remove 'view source code' from top of page (for html, not python)
)
add_module_names = False  # Remove namespaces from class/method signatures

autoapi_type = "python"
autoapi_dirs = ["../src"]
autoapi_ignore = ["*/__main__.py", "*/_version.py"]
autoapi_add_toc_tree_entry = False
autoapi_member_order = "bysource"

html_theme = "sphinx_rtd_theme"