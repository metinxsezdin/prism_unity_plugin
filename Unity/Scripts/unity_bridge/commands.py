"""Unity → Prism commands. Only names in COMMANDS can ever be dispatched."""

import inspect
import os

from . import protocol
from .headless import headless
from .protocol import BridgeError

COMMANDS = frozenset(
    {
        "ping",
        "projectBrowser",
        "settings",
        "saveVersion",
        "saveComment",
        "importDialog",
        "listProducts",
        "listVersions",
        "resolveVersion",
        "checkVersions",
        "checkVersionsDialog",
        "playblastDialog",
        "playblastTarget",
        "playblastDone",
    }
)


def _entity_label(entity):
    if entity.get("type") == "shot":
        return "%s/%s" % (entity.get("sequence"), entity.get("shot"))
    return entity.get("asset_path") or str(entity)


class PrismCommands(object):
    def __init__(self, core, unity):
        self.core = core
        self.unity = unity

    def dispatch(self, request):
        """Run one request and return a protocol response dict (never raises)."""
        request_id = request.get("id")
        cmd = request.get("cmd")
        fn = getattr(self, cmd, None) if cmd in COMMANDS else None
        if fn is None:
            return protocol.err(request_id, "unknown_command", "Unknown command: %s" % cmd)

        args = {k: v for k, v in (request.get("args") or {}).items() if not k.startswith("_")}
        try:
            inspect.signature(fn).bind(**args)
        except TypeError as e:
            return protocol.err(request_id, "bad_args", "Bad arguments for %s: %s" % (cmd, e))

        try:
            if request.get("interactive"):
                result = fn(**args)
            else:
                with headless(self.core):
                    result = fn(**args)
        except BridgeError as e:
            return e.to_response(request_id)
        return protocol.ok(request_id, result)

    # --- general -------------------------------------------------------------

    def ping(self):
        return {
            "prismVersion": getattr(self.core, "version", ""),
            "checkImportVersions": bool(self.core.getConfig("globals", "check_import_versions", dft=True)),
        }

    def projectBrowser(self):
        self.core.projectBrowser()
        return True

    def settings(self):
        self.core.prismSettings()
        return True

    # --- products ------------------------------------------------------------

    def listProducts(self, entity):
        return [{"product": p["product"], "entity": entity} for p in self.core.products.getProductsFromEntity(entity)]

    def listVersions(self, entity, product):
        return [self._describe_version(v) for v in self.core.products.getVersionsFromProduct(entity, product)]

    def resolveVersion(self, entity, product, version="latest"):
        products = self.core.products
        if version == "latest":
            found = products.getLatestVersionFromProduct(product, entity=entity, includeMaster=True)
        else:
            found = next((v for v in products.getVersionsFromProduct(entity, product) if v.get("version") == version), None)
        if not found:
            raise BridgeError(
                "source_unavailable",
                "Prism has no version '%s' of '%s' for %s." % (version, product, _entity_label(entity)),
            )
        described = self._describe_version(found)
        if not described["filepath"] or not os.path.isfile(described["filepath"]):
            raise BridgeError(
                "source_unavailable",
                "The file of %s %s is not reachable: %s" % (product, described["version"], described["filepath"] or found.get("path")),
            )
        return described

    def checkVersions(self, records):
        outdated = []
        for record in records:
            try:
                latest = self.resolveVersion(record["entity"], record["product"])["version"]
            except BridgeError:
                continue  # unreachable products are reported by the import itself, not here
            if latest != record.get("version"):
                outdated.append({"id": record["id"], "current": record.get("version"), "latest": latest,
                                 "entity": record["entity"], "product": record["product"]})
        return outdated

    def importDialog(self):
        from . import dialogs

        dialogs.open_import_browser(self)
        return True

    def checkVersionsDialog(self, quiet=False):
        """quiet=True (startup check): say nothing when everything is current."""
        from . import dialogs

        outdated = self.checkVersions(self.unity.call("listImported") or [])
        if outdated:
            dialogs.open_check_versions(self, outdated)
        elif not quiet:
            self.core.popup("All Prism imports in this Unity project are up to date.", title="Prism", severity="info")
        return outdated

    def _describe_version(self, version):
        products = self.core.products
        try:
            info = products.getVersionInfoFromVersion(version) or {}
        except Exception:
            info = {}
        try:
            filepath = products.getPreferredFileFromVersion(version) or ""
        except Exception:
            filepath = ""  # e.g. the project drive is offline; resolveVersion reports it
        return {
            "version": version.get("version"),
            "comment": info.get("comment") or "",
            "user": info.get("user") or info.get("username") or "",
            "date": info.get("date") or "",
            "filepath": filepath.replace("\\", "/"),
            "location": next(iter(version.get("locations") or {"global": None})),
        }
