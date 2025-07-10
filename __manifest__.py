# -*- coding: utf-8 -*-
{
    'name'     : 'Module OCR InfoSaône pour Odoo 18',
    'version'  : '0.1',
    'author'   : 'InfoSaône',
    'category' : 'InfoSaône',
    'description': """
Module OCR InfoSaône pour Odoo 18
===================================================
""",
    'maintainer' : 'InfoSaône',
    'website'    : 'http://www.infosaone.com',
    'depends'    : [
        'base',
        'mail',
    ],
    'data' : [
        'security/ir.model.access.csv',
        'views/res_company_view.xml',
        'views/is_ocr_view.xml',
        #'views/menu.xml',
    ],
    "assets": {
        'web.assets_backend': [
            'is_ocr_infosaone18/static/src/scss/style.scss',
         ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
