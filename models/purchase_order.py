from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

AREA_ORIGEN_SELECTION = [
    ('laboratorio', 'LABORATORIO'),
    ('compras', 'COMPRAS'),
    ('biologia_molecular', 'BIOLOGIA MOLECULAR'),
    ('control_calidad', 'CONTROL DE CALIDAD'),
    ('control_calidad_externo', 'CONTROL DE CALIDAD EXTERNO'),
    ('derivaciones_internacionales', 'DERIVACIONES INTERNACIONALES'),
    ('equipos', 'EQUIPOS'),
    ('generales', 'GENERALES'),
    ('hematologia', 'HEMATOLOGIA'),
    ('informatica', 'INFORMATICA'),
    ('microbiologia', 'MICROBIOLOGIA'),
    ('muebles_equipos', 'Muebles y Equipos'),
    ('procesos_especiales', 'PROCESOS ESPECIALES'),
    ('reparaciones', 'REPARACIONES'),
    ('toma_muestra', 'TOMA DE MUESTRA'),
]

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    is_sent = fields.Boolean(
        string="Order Sent",
        copy=False,
        help="Indicates if the purchase order has been sent to the vendor via email."
    )
    origin = fields.Char(copy=True)
    is_sent_label = fields.Char(string="Estado de Envío", compute="_compute_is_sent_label")
    origen_solicitante = fields.Selection(
        selection=AREA_ORIGEN_SELECTION,
        string="Área de Origen",
        required=False,
    )
    
    approved_user_ids = fields.Many2many(
        comodel_name='res.users',
        string='Usuarios que aprobaron',
        compute='_compute_approved_user_ids',
        store=True
    )
    approval_status = fields.Selection([
        ('untouch', 'Sin aprobaciones'),
        ('pending', 'Falta 1 aprobación'),
        ('complete', 'Totalmente aprobado')
    ], string='Estado de aprobación', compute='_compute_approval_status', store=True)
    
    @api.depends('message_ids')
    def _compute_approved_user_ids(self):
        ApprovalEntry = self.env['studio.approval.entry']
        for record in self:
            # Buscar entradas de aprobación para este registro
            approvals = ApprovalEntry.search([
                ('model', '=', 'purchase.order'),
                ('res_id', '=', record.id),
                ('user_id', '!=', False)
            ])
            user_ids = approvals.mapped('user_id').ids
            record.approved_user_ids = [(6, 0, user_ids)]

    @api.depends('approved_user_ids', 'state')
    def _compute_approval_status(self):
        for record in self:
            # Si ya está confirmada como orden de compra, se considera totalmente aprobada
            if record.state in ('purchase', 'done'):
                record.approval_status = 'complete'
            else:
                count = len(record.approved_user_ids)
                if count == 0:
                    record.approval_status = 'untouch'
                elif count == 1:
                    record.approval_status = 'pending'
                elif count >= 2:
                    record.approval_status = 'complete'
                else:
                    record.approval_status = 'untouch'

    @api.depends('is_sent')
    def _compute_is_sent_label(self):
        for record in self:
            record.is_sent_label = "Enviado" if record.is_sent else "No enviado"

    
    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        # Llamamos al método original primero
        result = super(PurchaseOrder, self).message_post(**kwargs)
    
        # Si se está marcando como enviada, actualizamos el campo is_sent
        if self.env.context.get('mark_rfq_as_sent'):
            self.filtered(lambda o: o.state in ('purchase', 'done')).write({'is_sent': True})
    
        return result