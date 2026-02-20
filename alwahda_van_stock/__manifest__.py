{
    'name': 'AL Wahda Van Stock',
    'version': '19.0.0.4',
    'description': "AL Wahda Van Stock",
    'author': 'AGM Global Services',
    'website': 'www.agmprojects.com',
    'summary': 'AL Wahda Van Stock',
    'depends': ['base', 'stock', 'point_of_sale', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/stock_van_request_sequence.xml',
        'views/stock_van_requests.xml',
        'views/stock_location.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'alwahda_van_stock/static/src/js/van_stock_screen.js',
            'alwahda_van_stock/static/src/xml/van_stock_templates.xml',
            'alwahda_van_stock/static/src/css/van_stock.css',
        ],
    },
    'installable': True
}
