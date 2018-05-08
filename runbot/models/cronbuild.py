# -*- coding: utf-8 -*-

import logging
from odoo import models, fields

_logger = logging.getLogger(__name__)

SECS = {'days': 24*3600, 'hours': 3600, 'weeks': 24*3600*7, 'months': 31*24*3600}


class runbot_cronbuild(models.Model):
    """ Model that permit to force an extra build on based on a cron """

    _name = 'runbot.cronbuild'

    repo_id = fields.Many2one('runbot.repo', 'Repository', required=True, ondelete='cascade')
    branch_id = fields.Many2one('runbot.branch', 'Branch', required=True, ondelete='cascade', index=True)
    frequence = fields.Selection([('hours', 'Hourly'),
                                  ('days', 'Daily'),
                                  ('weeks', 'Weekly'),
                                  ('months', 'Monthly')], string="Cron frequency", default='days')
    extra_params = fields.Char('Extra cmd args')
    last_build_date = fields.Datetime("Last build")

    def done(self):
        """ Check if the cron build was already called
        (e.g. from another runbot instance)
        """
        self.ensure_one()
        if not self.last_build_date:
            return False
        date_diff = fields.Datetime.from_string(fields.Datetime.now()) - fields.Datetime.from_string(self.last_build_date)
        max_seconds = SECS[self.frequence]
        return bool(date_diff.seconds < max_seconds)

    def _cron(self, freq):
        """ Generate extra builds when needed (called by cron's)"""
        build_model = self.env['runbot.build']
        for cronbuild in self.search([('frequence', '=', freq)]):
            last_build = build_model.search([('branch_id', '=', cronbuild.branch_id.id)],
                                            limit=1,
                                            order='sequence desc')
            if last_build and not cronbuild.done():
                build_model.with_context(force_rebuild=True).create({
                    'branch_id': cronbuild.branch_id.id,
                    'name': last_build.name,
                    'author': last_build.author,
                    'author_email': last_build.author_email,
                    'committer': last_build.committer,
                    'committer_email': last_build.committer_email,
                    'subject': last_build.subject,
                    'modules': last_build.modules,
                    'extra_params': cronbuild.extra_params
                })
                cronbuild.last_build_date = fields.Datetime.now()
