# -*- coding: utf-8 -*-

import os
import shutil
import subprocess
import tempfile

from odoo.tests import TransactionCase


class TestRunbotCronBuild(TransactionCase):
    def setUp(self):
        super().setUp()
        self.tmp_dir = tempfile.mkdtemp()

        @self.addCleanup
        def remove_tmp_dir():
            if os.path.isdir(self.tmp_dir):
                shutil.rmtree(self.tmp_dir)

        self.work_tree = os.path.join(self.tmp_dir, "git_example")
        self.git_dir = os.path.join(self.work_tree, ".git")
        subprocess.call(["git", "init", self.work_tree])
        hooks_dir = os.path.join(self.git_dir, "hooks")
        if os.path.isdir(hooks_dir):
            # Avoid run a hooks for commit commands
            shutil.rmtree(hooks_dir)
        self.repo = self.env["runbot.repo"].create({"name": self.git_dir})
        self.branch = self.env['runbot.branch'].create({
            'name': 'refs/heads/master',
            'branch_name': 'master',
            'repo_id': self.repo.id
        })
        self.build_model = self.env['runbot.build']
        self.cronbuild_model = self.env['runbot.cronbuild']

        @self.addCleanup
        def remove_clone_dir():
            if os.path.isdir(self.repo.path):
                shutil.rmtree(self.repo.path)

    def git(self, *cmd):
        subprocess.call(["git"] + list(cmd), cwd=self.work_tree)

    def test_cronbuild_generate_build(self):
        """ Test that a build is generated based on the last build """

        extra_params = '--test-tags nightly'
        cronbuild = self.cronbuild_model.create({
            'repo_id': self.repo.id,
            'branch_id': self.branch.id,
            'extra_params': extra_params,
        })
        # check that the frequence default value is 'days'
        self.assertEqual(cronbuild.frequence, 'days')

        cronbuild._cron('weeks')
        # check that no new builds were created from other crons
        self.assertEqual(self.build_model.search_count([]), 0)

        # check that no new builds are created at bootstrap
        cronbuild._cron('days')
        self.assertEqual(self.build_model.search_count([]), 0)

        msg = 'Initial commit'
        self.git("commit", "--allow-empty", "-m", msg)
        self.repo._update_git()
        first_build = self.build_model.search([("subject", "=", msg)])[0]
        cronbuild._cron('days')
        last_build = self.build_model.search([("subject", "=", msg)])[:-1]

        # check that a new build was generated
        self.assertNotEqual(first_build, last_build)
        self.assertEqual(last_build.extra_params, extra_params)
        self.assertEqual(last_build.state, 'pending')
        self.assertFalse(last_build.result)

        # Ensure that a new call (e.g. from another runbot instance) will not
        # generate a new build
        builds_count = self.build_model.search_count([])
        cronbuild._cron('days')
        self.assertEqual(self.build_model.search_count([]), builds_count)
