# -*- coding: utf-8 -*-
{
    'name': 'Tính Lương',
    'version': '1.0',
    'depends': ['nhan_su', 'cham_cong'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/cron_bang_luong.xml',
        'views/bang_luong_views.xml',
        'views/phieu_luong_views.xml',
    ],
    'installable': True,
    'application': True,
    'sequence': 186,
}
