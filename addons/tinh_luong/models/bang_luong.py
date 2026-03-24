# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class BangLuong(models.Model):
    _name = 'bang.luong'
    _description = 'Bảng Lương'

    name = fields.Char(string='Mã Bảng Lương', required=True, readonly=True, default=lambda self: 'New')
    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhân Viên', required=True, ondelete='restrict')
    thang = fields.Selection([(str(i), f'Tháng {i}') for i in range(1, 13)], string='Tháng', required=True)
    nam = fields.Integer(string='Năm', required=True, default=lambda self: fields.Date.today().year)
    
    # Dữ liệu từ chấm công
    tong_ngay_cong = fields.Float(string='Tổng Ngày Công')
    tong_phut_di_muon = fields.Float(string='Tổng Phút Đi Muộn')
    tong_phut_ve_som = fields.Float(string='Tổng Phút Về Sớm')
    tong_phat = fields.Float(string='Tổng Phạt')
    
    # Lương
    luong_co_ban = fields.Float(string='Lương Cơ Bản')
    luong_thuc_lanh = fields.Float(string='Lương Thực Lãnh', compute='_compute_luong_thuc_lanh', store=True)
    
    trang_thai = fields.Selection([('draft', 'Nháp'), ('done', 'Hoàn Thành')], default='draft', string='Trạng Thái')
    
    phieu_luong_ids = fields.One2many('phieu.luong', 'bang_luong_id', string='Phiếu Lương')
    
    @api.onchange('nhan_vien_id', 'thang', 'nam')
    def _onchange_compute_from_cham_cong(self):
        if self.nhan_vien_id and self.thang and self.nam:
            self.action_compute_from_cham_cong()
    
    @api.depends('luong_co_ban', 'tong_ngay_cong', 'tong_phat')
    def _compute_luong_thuc_lanh(self):
        for record in self:
            record.luong_thuc_lanh = max(0, (record.luong_co_ban * record.tong_ngay_cong) - record.tong_phat) if record.luong_co_ban and record.tong_ngay_cong else 0
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            seq_val = self.env['ir.sequence'].next_by_code('bang.luong')
            _logger.info(f"Sequence for bang.luong: {seq_val}")
            vals['name'] = seq_val or 'BL 1'
        record = super(BangLuong, self).create(vals)
        record.action_compute_from_cham_cong()
        return record
    
    def write(self, vals):
        res = super(BangLuong, self).write(vals)
        if any(key in vals for key in ['nhan_vien_id', 'thang', 'nam']):
            self.action_compute_from_cham_cong()
        return res
    
    def action_compute_from_cham_cong(self):
        """Tính lương từ dữ liệu chấm công"""
        for record in self:
            _logger.info(f"Tính lương cho nhân viên: {record.nhan_vien_id.ho_va_ten if record.nhan_vien_id else 'Không có'} tháng {record.thang}/{record.nam}")
            if not record.nhan_vien_id:
                _logger.warning("Không có nhân viên được chọn")
                continue  # Bỏ qua nếu không có nhân viên
            
            # Tìm dữ liệu chấm công
            bang_cham_cong_ids = self.env['bang_cham_cong'].search([
                ('nhan_vien_id', '=', record.nhan_vien_id.id),
                ('ngay_cham_cong', '>=', f'{record.nam}-{int(record.thang):02d}-01'),
                ('ngay_cham_cong', '<=', f'{record.nam}-{int(record.thang):02d}-31')
            ])
            _logger.info(f"Tìm thấy {len(bang_cham_cong_ids)} bản ghi chấm công")
            
            if not bang_cham_cong_ids:
                # Không có dữ liệu, set về 0
                record.tong_ngay_cong = 0
                record.tong_phut_di_muon = 0
                record.tong_phut_ve_som = 0
                record.tong_phat = 0
                _logger.info("Không có dữ liệu chấm công, set về 0")
                continue
            
            # Tính toán
            tong_ngay_cong = 0.0
            for r in bang_cham_cong_ids:
                if r.trang_thai in ['di_lam', 'di_muon', 've_som', 'di_muon_ve_som']:
                    if r.ca_lam in ['Sáng', 'Chiều']:
                        tong_ngay_cong += 0.5
                    else:
                        tong_ngay_cong += 1.0

            tong_phut_di_muon = sum(r.phut_di_muon for r in bang_cham_cong_ids)
            tong_phut_ve_som = sum(r.phut_ve_som for r in bang_cham_cong_ids)
            tong_phat = (tong_phut_di_muon * 10000) + (tong_phut_ve_som * 5000)  # 10k/phút muộn, 5k/phút về sớm
            
            _logger.info(f"Tổng ngày công: {tong_ngay_cong}, Tổng phạt: {tong_phat}")
            
            # Cập nhật record
            record.tong_ngay_cong = tong_ngay_cong
            record.tong_phut_di_muon = tong_phut_di_muon
            record.tong_phut_ve_som = tong_phut_ve_som
            record.tong_phat = tong_phat

    @api.model
    def cron_refresh_bang_luong(self):
        """Tự động cập nhật tất cả bảng lương theo dữ liệu chấm công (không cần sửa cham_cong)."""
        self.search([]).action_compute_from_cham_cong()
        _logger.info("cron_refresh_bang_luong: đã cập nhật tất cả bang.luong")
        return True


class PhieuLuong(models.Model):
    _name = 'phieu.luong'
    _description = 'Phiếu Lương'

    name = fields.Char(string='Mã Phiếu', required=True, readonly=True, default=lambda self: 'New')
    bang_luong_id = fields.Many2one('bang.luong', string='Bảng Lương', ondelete='cascade')
    nhan_vien_id = fields.Many2one('nhan_vien', string='Nhân Viên', related='bang_luong_id.nhan_vien_id', store=True, readonly=True)
    thang = fields.Selection([(str(i), f'Tháng {i}') for i in range(1, 13)], string='Tháng', related='bang_luong_id.thang', store=True, readonly=True)
    nam = fields.Integer(string='Năm', related='bang_luong_id.nam', store=True, readonly=True)
    
    luong_co_ban = fields.Float(string='Lương Cơ Bản', related='bang_luong_id.luong_co_ban', store=True, readonly=True)
    so_ngay_cong = fields.Float(string='Số Ngày Công', related='bang_luong_id.tong_ngay_cong', store=True, readonly=True)
    phat_di_muon = fields.Float(string='Phạt Đi Muộn', compute='_compute_phat', store=True)
    phat_ve_som = fields.Float(string='Phạt Về Sớm', compute='_compute_phat', store=True)
    tong_phat = fields.Float(string='Tổng Phạt', compute='_compute_tong_phat', store=True)
    luong_net = fields.Float(string='Lương Net', compute='_compute_luong_net', store=True)
    
    trang_thai = fields.Selection([('draft', 'Nháp'), ('done', 'Hoàn Thành')], default='draft', string='Trạng Thái')
    
    @api.onchange('bang_luong_id')
    def _onchange_bang_luong_id(self):
        # Force compute các field related
        self._compute_phat()
    
    @api.depends('bang_luong_id.tong_phut_di_muon', 'bang_luong_id.tong_phut_ve_som')
    def _compute_phat(self):
        for record in self:
            record.phat_di_muon = (record.bang_luong_id.tong_phut_di_muon or 0) * 10000
            record.phat_ve_som = (record.bang_luong_id.tong_phut_ve_som or 0) * 5000
    
    @api.depends('phat_di_muon', 'phat_ve_som')
    def _compute_tong_phat(self):
        for record in self:
            record.tong_phat = (record.phat_di_muon or 0) + (record.phat_ve_som or 0)
    
    @api.depends('luong_co_ban', 'so_ngay_cong', 'tong_phat')
    def _compute_luong_net(self):
        for record in self:
            record.luong_net = max(0, (record.luong_co_ban * record.so_ngay_cong) - record.tong_phat) if record.luong_co_ban and record.so_ngay_cong else 0
    
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('phieu.luong') or 'PL 1'
        return super(PhieuLuong, self).create(vals)
