# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Bioinformatics Tools'
copyright = '2025, Dane Deemer'
author = 'Dane Deemer'
release = '0.2.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = []

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'alabaster'
html_static_path = ['_static']
html_css_files = ['custom.css']

# Configure sidebar to always show global table of contents
html_sidebars = {
    '**': [
        'about.html',
        'navigation.html',
        'localtoc.html',  # Shows global TOC across all pages
        'relations.html',
        'searchbox.html',
    ]
}
