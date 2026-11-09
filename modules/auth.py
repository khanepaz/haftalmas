# -*- coding: utf-8 -*-
"""Users, roles and password handling (sha256 + per-user salt)."""
from __future__ import print_function, unicode_literals

import binascii
import hashlib
import io
import json
import os

ROLE_ADMIN = u"admin"
ROLE_USER = u"user"
ROLES = [ROLE_ADMIN, ROLE_USER]
ROLE_TITLES = {ROLE_ADMIN: u"Administrator", ROLE_USER: u"User"}

MIN_PASSWORD = 4


class AuthManager(object):
    def __init__(self, path):
        self.path = path
        self.users = []
        self._load()
        if not self.users:
            self.users.append(self._make(u"admin", u"admin", ROLE_ADMIN))
            try:
                self._save()
            except ValueError:
                # read-only folder and no users file: do NOT leave a default admin in memory
                self.users = []

    # -- persistence
    def _load(self):
        if not os.path.isfile(self.path):
            return
        try:
            with io.open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            users = data.get("users", [])
            self.users = [u for u in users
                          if u.get("username") and u.get("hash") and u.get("role") in ROLES]
        except (ValueError, IOError, OSError):
            self.users = []

    def _save(self):
        try:
            tmp = self.path + ".tmp"
            with io.open(tmp, "w", encoding="utf-8") as f:
                f.write(json.dumps({"users": self.users}, indent=2, ensure_ascii=False))
            os.replace(tmp, self.path)
        except (IOError, OSError) as e:
            raise ValueError(u"Cannot save the users file (is the program folder read-only?):\n%s\n%s" % (self.path, e))

    # -- helpers
    @staticmethod
    def _hash(salt, password):
        return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()

    def _make(self, username, password, role):
        salt = binascii.hexlify(os.urandom(8)).decode("ascii")
        return {"username": username, "salt": salt,
                "hash": self._hash(salt, password), "role": role}

    def _find(self, username):
        key = (username or u"").strip().lower()
        for u in self.users:
            if u["username"].lower() == key:
                return u
        return None

    def _admin_count(self):
        return sum(1 for u in self.users if u["role"] == ROLE_ADMIN)

    # -- public API
    def authenticate(self, username, password):
        """Return the role on success, otherwise None."""
        u = self._find(username)
        if u is None:
            return None
        if self._hash(u.get("salt", u""), password or u"") == u["hash"]:
            return u["role"]
        return None

    def canonical_name(self, username):
        u = self._find(username)
        return u["username"] if u else username

    def uses_default_password(self):
        u = self._find(u"admin")
        return bool(u and self._hash(u.get("salt", u""), u"admin") == u["hash"])

    def list_users(self):
        return [(u["username"], u["role"]) for u in
                sorted(self.users, key=lambda x: x["username"].lower())]

    def add_user(self, username, password, role):
        username = (username or u"").strip()
        if not username:
            raise ValueError(u"Username is required.")
        if role not in ROLES:
            raise ValueError(u"Invalid role.")
        if len(password or u"") < MIN_PASSWORD:
            raise ValueError(u"Password must be at least %d characters." % MIN_PASSWORD)
        if self._find(username) is not None:
            raise ValueError(u"User '%s' already exists." % username)
        self.users.append(self._make(username, password, role))
        self._save()

    def delete_user(self, username):
        u = self._find(username)
        if u is None:
            raise ValueError(u"User not found.")
        if u["role"] == ROLE_ADMIN and self._admin_count() <= 1:
            raise ValueError(u"The last administrator cannot be deleted.")
        self.users.remove(u)
        self._save()

    def set_role(self, username, role):
        u = self._find(username)
        if u is None:
            raise ValueError(u"User not found.")
        if role not in ROLES:
            raise ValueError(u"Invalid role.")
        if u["role"] == ROLE_ADMIN and role != ROLE_ADMIN and self._admin_count() <= 1:
            raise ValueError(u"The last administrator cannot be demoted.")
        u["role"] = role
        self._save()

    def reset_password(self, username, new_password):
        u = self._find(username)
        if u is None:
            raise ValueError(u"User not found.")
        if len(new_password or u"") < MIN_PASSWORD:
            raise ValueError(u"Password must be at least %d characters." % MIN_PASSWORD)
        salt = binascii.hexlify(os.urandom(8)).decode("ascii")
        u["salt"] = salt
        u["hash"] = self._hash(salt, new_password)
        self._save()
