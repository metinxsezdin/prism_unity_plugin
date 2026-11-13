"""Posts new Trello board activity to Discord channels through webhooks.

Run every few minutes (Windows Task Scheduler, pythonw.exe so no window opens). Settings are in config.json next to
this file: {"trelloKey", "trelloToken", "boards": {"<board id or short link>": "<Discord webhook URL>"}}.
state.json remembers what was already posted, so activity while the computer was off is posted on the next run.
The first run of a board only records where it is; nothing old is posted.

    python trello_discord.py            post new activity
    python trello_discord.py --dry-run  print what would be posted, change nothing
    python trello_discord.py --hello    post a "connected" message to every channel
    python trello_discord.py --summary  post the daily summary now (with --dry-run: print it)

Optional in config.json: "summary": {"webhook": "<URL>", "time": "09:30"} posts a daily overview on weekdays.
"""

import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "config.json")
STATE = os.path.join(HERE, "state.json")
LOG = os.path.join(HERE, "trello_discord.log")
UA = "trello-discord-sync/1.0"

FILTER = ",".join([
    "createCard", "copyCard", "updateCard:idList", "updateCard:closed", "commentCard",
    "addMemberToCard", "removeMemberFromCard", "updateCheckItemStateOnCard", "addAttachmentToCard",
    "moveCardToBoard",
])
COLORS = {"new": 0x2ECC71, "move": 0x3498DB, "comment": 0xF1C40F, "member": 0x9B59B6,
          "check": 0x1ABC9C, "attach": 0xE67E22, "archive": 0x95A5A6}


def log(message):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("%s %s\n" % (datetime.datetime.now().isoformat(timespec="seconds"), message))


def http(url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET",
                                 headers={"User-Agent": UA, "Content-Type": "application/json"})
    for _ in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(float(e.headers.get("Retry-After") or 2) + 0.5)
                continue
            raise RuntimeError("%s -> %s %s" % (url.split("?")[0], e.code, e.read()[:300]))
    raise RuntimeError("rate limited: %s" % url.split("?")[0])


def trello(cfg, path, **params):
    params.update(key=cfg["trelloKey"], token=cfg["trelloToken"])
    return http("https://api.trello.com/1/%s?%s" % (path, urllib.parse.urlencode(params)))


def describe(action):
    """(kind, sentence) in Turkish for one Trello action, or None to skip it."""
    t, d = action["type"], action["data"]
    who = "**%s**" % action.get("memberCreator", {}).get("fullName", "Biri")
    card = "**%s**" % d.get("card", {}).get("name", "?")
    if t == "moveCardToBoard":
        return "new", "%s %s kartını başka panodan *%s* listesine getirdi." % (who, card, d.get("list", {}).get("name", "?"))
    if t in ("createCard", "copyCard"):
        return "new", "%s %s kartını *%s* listesinde açtı." % (who, card, d.get("list", {}).get("name", "?"))
    if t == "updateCard" and "listAfter" in d:
        return "move", "%s %s kartını *%s* → *%s* listesine taşıdı." % (who, card, d["listBefore"]["name"], d["listAfter"]["name"])
    if t == "updateCard" and "closed" in d.get("old", {}):
        return "archive", "%s %s kartını %s." % (who, card, "arşivledi" if d["card"].get("closed") else "arşivden çıkardı")
    if t == "commentCard":
        text = d.get("text", "")
        return "comment", "%s %s kartına yorum yazdı:\n> %s" % (who, card, text[:1500].replace("\n", "\n> "))
    if t == "addMemberToCard":
        return "member", "%s, **%s** kişisini %s kartına atadı." % (who, action.get("member", {}).get("fullName", "?"), card)
    if t == "removeMemberFromCard":
        return "member", "%s, **%s** kişisini %s kartından çıkardı." % (who, action.get("member", {}).get("fullName", "?"), card)
    if t == "updateCheckItemStateOnCard":
        item = d.get("checkItem", {})
        if item.get("state") == "complete":
            return "check", "%s %s kartında ✅ tamamladı: %s" % (who, card, item.get("name", "?"))
        return "check", "%s %s kartında işareti kaldırdı: %s" % (who, card, item.get("name", "?"))
    if t == "addAttachmentToCard":
        a = d.get("attachment", {})
        name = a.get("name") or "dosya"
        link = "[%s](%s)" % (name, a["url"]) if a.get("url") else name
        return "attach", "%s %s kartına ekledi: %s" % (who, card, link)
    return None


def embed(action, kind, sentence, board_name):
    d = action["data"]
    short = d.get("card", {}).get("shortLink")
    e = {"description": sentence, "color": COLORS[kind], "timestamp": action["date"],
         "footer": {"text": board_name}}
    if short:
        e["url"] = "https://trello.com/c/%s" % short
        e["title"] = d["card"].get("name", "")[:250]
    return e


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_state(state):
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE)


def run(dry_run=False):
    cfg = load(CONFIG, None)
    state = load(STATE, {})
    for board, hook in cfg["boards"].items():
        info = trello(cfg, "boards/%s" % board, fields="name")
        mark = state.get(board)
        if mark is None:  # first run: start from now
            latest = trello(cfg, "boards/%s/actions" % board, filter=FILTER, limit=1)
            state[board] = {"since": latest[0]["date"] if latest else datetime.datetime.utcnow().isoformat() + "Z",
                            "seen": [a["id"] for a in latest]}
            if not dry_run:
                save_state(state)
            continue
        actions = [a for a in reversed(trello(cfg, "boards/%s/actions" % board, filter=FILTER, since=mark["since"], limit=100))
                   if a["id"] not in mark["seen"]]  # oldest first
        if not actions:
            continue
        people = state.get("people", {})
        for body, pings in messages(cfg, actions, info["name"], people):
            body = prepare(body, pings)
            if dry_run:
                print(json.dumps(body, ensure_ascii=False))
            else:
                http(hook, body)
        if not dry_run:  # saved once per board: a failed post repeats the run rather than losing activity
            mark["since"] = actions[-1]["date"]
            mark["seen"] = (mark["seen"] + [a["id"] for a in actions])[-200:]
            save_state(state)


SILENT = 1 << 12  # Discord's SUPPRESS_NOTIFICATIONS (@silent): shows in the channel, no push notification


def prepare(body, pings=()):
    """A message that notifies only the given Discord users; with nobody to notify it is sent silently."""
    body = dict(body)
    pings = [p for p in dict.fromkeys(pings) if p]
    if pings:
        body["content"] = (" ".join("<@%s>" % p for p in pings) + " " + body.get("content", "")).strip()
        body["allowed_mentions"] = {"users": pings}
    else:
        body["flags"] = SILENT
        body["allowed_mentions"] = {"parse": []}
    return body


def card_members(cfg, card_id):
    try:
        return trello(cfg, "cards/%s" % card_id, fields="idMembers")["idMembers"]
    except RuntimeError:  # deleted meanwhile
        return []


def pings_for(cfg, action, people):
    """Discord ids to notify about an action: the person it concerns, never the one who did it."""
    actor = action.get("idMemberCreator")
    t, d = action["type"], action["data"]
    if t == "addMemberToCard":
        targets = [action.get("member", {}).get("id") or d.get("idMember")]
    elif t == "commentCard" or (t == "updateCard" and "listAfter" in d):
        targets = card_members(cfg, d["card"]["id"])
    else:
        return []
    return [people[m] for m in targets if m and m != actor and m in people]


def messages(cfg, actions, board_name, people=None):
    """[(Discord message, Discord ids to notify)] for actions (oldest first).

    Checklist ticks of one person on one card become one message.
    """
    people = people or {}
    out, ticks = [], {}
    for action in actions:
        if action["type"] == "updateCheckItemStateOnCard":
            key = (action["data"]["card"]["id"], action.get("idMemberCreator"))
            if key not in ticks:
                ticks[key] = []
                out.append(("ticks", key))
            ticks[key].append(action)
        else:
            out.append(("one", action))
    bodies = []
    for kind, item in out:
        if kind == "one":
            found = describe(item)
            if found:
                bodies.append(({"username": "Trello", "embeds": [embed(item, found[0], found[1], board_name)]},
                               pings_for(cfg, item, people)))
            continue
        group = ticks[item]
        if len(group) == 1:
            found = describe(group[0])
            bodies.append(({"username": "Trello", "embeds": [embed(group[0], found[0], found[1], board_name)]}, []))
            continue
        last = group[-1]
        # Per item only the net change: ticked and unticked again in the same run is no change.
        per_item = {}
        for a in group:
            per_item.setdefault(a["data"]["checkItem"]["id"], []).append(a["data"]["checkItem"])
        net = [states[-1] for states in per_item.values() if len(states) % 2 == 1]
        if not net:
            continue
        done = [i["name"] for i in net if i.get("state") == "complete"]
        undone = [i["name"] for i in net if i.get("state") != "complete"]
        who = last.get("memberCreator", {}).get("fullName", "Biri")
        lines = ["**%s** **%s** kartında" % (who, last["data"]["card"]["name"])]
        if done:
            lines[0] += " %d madde tamamladı" % len(done)
        if undone:
            lines[0] += "%s %d maddenin işaretini kaldırdı" % (" ve" if done else "", len(undone))
        lines[0] += progress(cfg, last["data"]["card"]["id"]) + ":"
        lines += ["✅ %s" % n for n in done[:15]] + ["⬜ %s" % n for n in undone[:15]]
        if len(done) > 15 or len(undone) > 15:
            lines.append("…")
        bodies.append(({"username": "Trello", "embeds": [embed(last, "check", "\n".join(lines), board_name)]}, []))
    return bodies


def progress(cfg, card_id):
    try:
        items = [i for cl in trello(cfg, "cards/%s/checklists" % card_id, fields="name") for i in cl["checkItems"]]
    except RuntimeError:  # card deleted meanwhile
        return ""
    return " (%d/%d)" % (sum(i["state"] == "complete" for i in items), len(items)) if items else ""


# --- Prism: publishes and playblasts -------------------------------------------------------------------

MARKERS = {"Export": "publish", "Playblasts": "playblast"}
MEDIA = (".mp4", ".mov", ".png", ".jpg", ".jpeg", ".gif")
MAX_UPLOAD = 9 * 1024 * 1024  # Discord's limit for servers without boosts is 10 MB


def prism_versions(root):
    """{versioninfo path: (kind, entity, product or task, version folder)} of every non-master version under root."""
    found = {}
    production = os.path.join(root, "03_Production")
    for folder, dirs, files in os.walk(production):
        dirs[:] = [d for d in dirs if d != "master" and not d.startswith(".")]
        if "versioninfo.json" not in files:
            continue
        parts = os.path.relpath(folder, production).replace("\\", "/").split("/")
        marker = next((i for i, p in enumerate(parts) if p in MARKERS), None)
        if marker is None or marker + 2 >= len(parts):
            continue
        entity = "/".join(parts[1:marker]) if parts[0] == "Assets" else "/".join(parts[:marker])
        found[os.path.join(folder, "versioninfo.json")] = (MARKERS[parts[marker]], entity, parts[marker + 1], folder)
        dirs[:] = []  # nothing versioned below a version folder
    return found


def media_file(folder):
    """The file to show for a playblast version: the video, or the middle frame of an image sequence."""
    files = sorted(os.path.join(dp, f) for dp, _, fs in os.walk(folder) for f in fs if f.lower().endswith(MEDIA))
    videos = [f for f in files if f.lower().endswith((".mp4", ".mov", ".gif"))]
    if videos:
        return videos[0]
    return files[len(files) // 2] if files else None


def post_with_file(url, payload, path):
    """Webhook post with one attached file (multipart); without the file when it is too big."""
    if not path or os.path.getsize(path) > MAX_UPLOAD:
        return http(url, payload)
    boundary = "----prism%d" % int(time.time() * 1000)
    with open(path, "rb") as f:
        data = f.read()
    name = os.path.basename(path)
    body = b"".join([
        ("--%s\r\nContent-Disposition: form-data; name=\"payload_json\"\r\nContent-Type: application/json\r\n\r\n" % boundary).encode(),
        json.dumps(payload).encode(), b"\r\n",
        ("--%s\r\nContent-Disposition: form-data; name=\"files[0]\"; filename=\"%s\"\r\nContent-Type: application/octet-stream\r\n\r\n"
         % (boundary, name)).encode("utf-8"),
        data, ("\r\n--%s--\r\n" % boundary).encode()])
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "User-Agent": UA, "Content-Type": "multipart/form-data; boundary=%s" % boundary})
    for _ in range(5):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(float(e.headers.get("Retry-After") or 2) + 0.5)
                continue
            raise RuntimeError("upload -> %s %s" % (e.code, e.read()[:300]))


def asset_card(cfg, conf, asset):
    """The asset's card on the 3D board (same name, not the template), or None."""
    for card in trello(cfg, "boards/%s/cards" % conf["trelloBoard"], fields="name,idList,isTemplate,idMembers"):
        if not card.get("isTemplate") and card["name"].strip().lower() == asset.lower():
            return card
    return None


def playblast_pings(cfg, conf, card, maker, people):
    """Discord ids of the card's members, except the person who made the playblast (matched by full name)."""
    if not card:
        return []
    names = {m["id"]: m["fullName"].strip().lower()
             for m in trello(cfg, "boards/%s/members" % conf["trelloBoard"], fields="fullName")}
    return [people[m] for m in card["idMembers"] if m in people and names.get(m) != maker.strip().lower()]


def find_thread(cfg, conf, asset):
    """Id of a #review forum post named like the asset (someone may have opened it by hand), or None.

    Needs the bot token (cards.botToken); without it only the posts this script opened are known.
    """
    bot_conf, forum = cfg.get("cards") or {}, conf.get("reviewChannel")
    if not bot_conf.get("botToken") or not forum:
        return None
    guild = conf.get("guild")
    threads = discord_bot(bot_conf, "GET", "/guilds/%s/threads/active" % guild)["threads"] if guild else []
    threads += discord_bot(bot_conf, "GET", "/channels/%s/threads/archived/public?limit=100" % forum)["threads"]
    for th in threads:
        if th.get("parent_id") == forum and th["name"].strip().lower() == asset.lower():
            return th["id"]
    return None


def trello_to_review(cfg, conf, card, link):
    """Move the asset's card to Review (only from an earlier list) and leave the link as a comment."""
    lists = {l["id"]: l["name"] for l in trello(cfg, "boards/%s/lists" % conf["trelloBoard"], fields="name")}
    review = next((i for i, n in lists.items() if n == conf["reviewList"]), None)
    if review and lists.get(card["idList"]) in conf.get("beforeReview", []):
        params = dict(idList=review, pos="bottom", key=cfg["trelloKey"], token=cfg["trelloToken"])
        http_put("https://api.trello.com/1/cards/%s?%s" % (card["id"], urllib.parse.urlencode(params)))
    params = dict(text="🎬 Yeni playblast: %s" % link, key=cfg["trelloKey"], token=cfg["trelloToken"])
    http_put("https://api.trello.com/1/cards/%s/actions/comments?%s" % (card["id"], urllib.parse.urlencode(params)), method="POST")


def http_put(url, method="PUT"):
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read() or b"null")


def prism_run(dry_run=False):
    cfg = load(CONFIG, None)
    conf = cfg.get("prism") or {}
    root = conf.get("project")
    if not root:
        return
    if not os.path.isdir(root):  # drive offline: try again next run, nothing is lost
        return
    state = load(STATE, {})
    seen = state.get("prism")
    versions = prism_versions(root)
    if seen is None or seen.get("project") != root:  # first run for this project: remember, post nothing
        state["prism"] = {"project": root, "seen": sorted(versions), "threads": (seen or {}).get("threads", {})}
        if not dry_run:
            save_state(state)
        return
    known = set(seen["seen"])
    for path in sorted((p for p in versions if p not in known), key=lambda p: os.path.getmtime(p)):
        kind, entity, name, folder = versions[path]
        info = load(path, {})
        if not info:  # still being written; next run
            continue
        who = info.get("username") or info.get("user") or "Biri"
        version = info.get("version") or os.path.basename(folder)
        comment = (info.get("comment") or "").strip()
        asset = entity.split("/")[-1]
        if kind == "publish":
            text = "📦 **%s**, **%s** için `%s` **%s** publish etti." % (who, entity, name, version)
            if comment:
                text += "\n> %s" % comment
            text += "\nUnity'de *Prism → Check for New Versions...* ile alabilirsiniz."
            body = {"username": "Prism", "embeds": [{"description": text, "color": 0x8E44AD}]}
            if dry_run:
                print(json.dumps(prepare(body), ensure_ascii=False))
            else:
                http(conf["wipWebhook"], prepare(body))
        else:
            text = "🎬 **%s**, **%s** için yeni playblast: `%s` **%s**" % (who, entity, name, version)
            if comment:
                text += "\n> %s" % comment
            media = media_file(folder)
            if media and os.path.getsize(media) > MAX_UPLOAD:
                text += "\n(Dosya Discord için büyük: `%s`)" % media.replace("\\", "/")
            try:
                card = asset_card(cfg, conf, asset)
                pings = playblast_pings(cfg, conf, card, who, state.get("people", {}))
            except Exception as e:  # Trello down: still post the playblast, just without the card
                log("trello lookup failed for %s: %r" % (asset, e))
                card, pings = None, []
            payload = prepare({"username": "Prism", "content": text}, pings)
            thread = seen["threads"].get(asset)
            if not thread:
                try:
                    thread = find_thread(cfg, conf, asset)
                except Exception as e:  # lookup is a nicety; worst case a second post with the same name
                    log("thread lookup failed for %s: %r" % (asset, e))
            url = conf["reviewWebhook"] + "?wait=true"
            if thread:
                url += "&thread_id=%s" % thread
            else:
                payload["thread_name"] = asset
                if conf.get("reviewTag"):
                    payload["applied_tags"] = [conf["reviewTag"]]
            if dry_run:
                print(json.dumps(payload, ensure_ascii=False), media)
            else:
                try:
                    msg = post_with_file(url, payload, media)
                except RuntimeError as e:
                    if not thread or "10003" not in str(e):  # 10003: the thread was deleted; open a new one
                        raise
                    seen["threads"].pop(asset, None)
                    payload["thread_name"] = asset
                    msg = post_with_file(conf["reviewWebhook"] + "?wait=true", payload, media)
                seen["threads"][asset] = msg["channel_id"]
                link = "https://discord.com/channels/%s/%s/%s" % (conf.get("guild", ""), msg["channel_id"], msg["id"]) \
                    if conf.get("guild") else "Discord #review → %s" % asset
                try:
                    if card:
                        trello_to_review(cfg, conf, card, link)
                except Exception as e:  # the Discord post is the main thing; Trello is a convenience
                    log("trello review move failed for %s: %r" % (asset, e))
        if not dry_run:
            seen["seen"].append(path)
            save_state(state)


# --- Trello → Prism: an asset for every card -----------------------------------------------------------

import subprocess


def trello_comment(cfg, card_id, text):
    http_put("https://api.trello.com/1/cards/%s/actions/comments?%s" % (card_id, urllib.parse.urlencode(
        dict(text=text, key=cfg["trelloKey"], token=cfg["trelloToken"]))), method="POST")


def set_prism_line(cfg, card, line):
    """Write the card description's 'Prism asset:' line (no notification, unlike a comment)."""
    import re as _re
    desc = card.get("desc") or ""
    pattern = _re.compile(r"^\*\*Prism asset:\*\*.*$", _re.M)
    new = pattern.sub(lambda _: line, desc, count=1) if pattern.search(desc) else (line + "\n" + desc).strip()
    if new != desc:
        http_put("https://api.trello.com/1/cards/%s?%s" % (card["id"], urllib.parse.urlencode(
            dict(desc=new, key=cfg["trelloKey"], token=cfg["trelloToken"]))))


def run_prism_create(conf, assets):
    """Create Prism assets in a child process (Prism boots there, without windows); its JSON answer."""
    helper = os.path.join(HERE, "prism_create.py")
    request = {"mcp": conf["mcp"], "project": conf["project"], "assets": assets}
    proc = subprocess.run([sys.executable, "-I", helper], input=json.dumps(request).encode("utf-8"),
                          capture_output=True, timeout=600, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        return json.loads(proc.stdout.decode("utf-8"))
    except ValueError:
        return {"ok": False, "error": "prism_create exited %s: %s" % (proc.returncode, proc.stderr.decode("utf-8", "replace")[-500:])}


def prism_create_run(dry_run=False):
    """Every 3D card with a valid name and one category label gets a Prism asset (Category/Name)."""
    cfg = load(CONFIG, None)
    conf = cfg.get("prism") or {}
    cats = conf.get("categories") or {}
    if not conf.get("project") or not conf.get("mcp") or not cats or not os.path.isdir(conf["project"]):
        return
    state = load(STATE, {})
    done = state.setdefault("prismCreated", {})   # card id -> {"path", "name"}
    warned = state.setdefault("prismWarned", {})  # card id -> what was said, so it is said once
    labels = {l["id"]: l["name"] for l in trello(cfg, "boards/%s/labels" % conf["trelloBoard"], fields="name")}
    todo = []
    for card in trello(cfg, "boards/%s/cards" % conf["trelloBoard"], fields="name,idLabels,isTemplate,desc"):
        if card.get("isTemplate"):
            continue
        name = card["name"].strip()
        if card["id"] in done:
            was = done[card["id"]]
            if name != was["name"] and warned.get(card["id"]) != "renamed:" + name:
                if not dry_run:
                    trello_comment(cfg, card["id"], "⚠️ Bu kartın adı değişti ama Prism asset'lerin adını değiştiremiyor. "
                                   "Prism'de hâlâ **%s**. Kartın adını geri al ya da Prism'de yeni asset açıp eskisini kaldır." % was["path"])
                warned[card["id"]] = "renamed:" + name
            continue
        found = [cats[labels[i]] for i in card["idLabels"] if labels.get(i) in cats]
        if not NAME_OK.match(name):
            if warned.get(card["id"]) != "name:" + name and not dry_run:
                trello_comment(cfg, card["id"], "⚠️ Prism'de asset açılamadı: ad sadece İngilizce harf, rakam, `_` ve `-` "
                               "içerebilir (Türkçe karakter ve boşluk yok). Kartın adını düzeltince kendiliğinden açılır.")
            warned[card["id"]] = "name:" + name
            continue
        if len(found) != 1:
            if len(found) > 1 and warned.get(card["id"]) != "labels" and not dry_run:
                trello_comment(cfg, card["id"], "⚠️ Kartta birden fazla tür etiketi var (%s). Prism'de asset açılabilmesi için "
                               "tek tür bırak." % ", ".join(sorted(k for k in cats if k in [labels.get(i) for i in card["idLabels"]])))
                warned[card["id"]] = "labels"
            continue  # no type label yet: wait for it
        todo.append((card, "%s/%s" % (found[0], name)))
    if not todo:
        if not dry_run:
            save_state(state)
        return
    if dry_run:
        print("would create in Prism:", [p for _, p in todo])
        return
    answer = run_prism_create(conf, [{"asset_path": p, "taskPreset": conf.get("taskPreset", "")} for _, p in todo])
    if not answer.get("ok"):
        save_state(state)
        raise RuntimeError("Prism: %s" % answer.get("error"))
    results = {r["asset_path"]: r for r in answer["results"]}
    for card, path in todo:
        r = results.get(path) or {}
        if r.get("ok"):
            done[card["id"]] = {"path": path, "name": card["name"].strip()}
            warned.pop(card["id"], None)
            set_prism_line(cfg, card, "**Prism asset:** %s ✅" % path)
        else:
            log("prism create %s failed: %s" % (path, r.get("error")))
    save_state(state)


# --- Discord → Trello: new cards from #kart-aç ---------------------------------------------------------

import re

NAME_OK = re.compile(r"^[A-Za-z0-9_-]+$")


def discord_bot(conf, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request("https://discord.com/api/v10" + path, data=data, method=method, headers={
        "Authorization": "Bot " + conf["botToken"], "User-Agent": "DiscordBot (local, 1.0)", "Content-Type": "application/json"})
    for _ in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(float(json.loads(e.read() or b"{}").get("retry_after", 2)) + 0.5)
                continue
            raise RuntimeError("discord %s %s -> %s %s" % (method, path, e.code, e.read()[:300]))


def cards_run(dry_run=False):
    """Every message in the card channel is an asset name (plus an optional type label): a card is made from the template."""
    cfg = load(CONFIG, None)
    conf = cfg.get("cards")
    if not conf or not conf.get("botToken"):
        return
    state = load(STATE, {})
    channel = conf["channel"]
    last = state.get("cardsLast")
    if last is None:  # first run: start after the newest message
        newest = discord_bot(conf, "GET", "/channels/%s/messages?limit=1" % channel)
        state["cardsLast"] = newest[0]["id"] if newest else "0"
        if not dry_run:
            save_state(state)
        return
    msgs = discord_bot(conf, "GET", "/channels/%s/messages?after=%s&limit=50" % (channel, last))
    if not msgs:
        return
    board = conf["board"]
    lists = {l["name"]: l["id"] for l in trello(cfg, "boards/%s/lists" % board, fields="name")}
    labels = {l["name"].lower(): l["id"] for l in trello(cfg, "boards/%s/labels" % board, fields="name") if l["name"]}
    cards = trello(cfg, "boards/%s/cards" % board, fields="name,isTemplate,shortUrl")
    template = next((c for c in cards if c.get("isTemplate")), None)
    for m in sorted(msgs, key=lambda m: int(m["id"])):
        if m["author"].get("bot") or m.get("webhook_id"):
            state["cardsLast"] = m["id"]
            continue
        words = (m.get("content") or "").split()
        found_labels = [labels[w.lower()] for w in words if w.lower() in labels]
        names = [w for w in words if w.lower() not in labels]
        people = state.setdefault("people", {})
        if not words:
            reply = None  # e.g. only an image; Message Content intent missing also lands here
        elif words[0].lower() in ("bağla", "bagla"):
            reply = link_person(cfg, people, m["author"]["id"], words[1:])
        elif len(names) != 1 or not NAME_OK.match(names[0]):
            reply = ("❌ Kart açılmadı. Bir asset adı yaz, istersen yanına türünü ekle: `Lotus Prop`.\n"
                     "Ad sadece İngilizce harf, rakam, `_` ve `-` içerebilir (Türkçe karakter ve boşluk yok).")
        else:
            name = names[0]
            same = next((c for c in cards if not c.get("isTemplate") and c["name"].lower() == name.lower()), None)
            if same:
                reply = "ℹ️ **%s** kartı zaten var: %s" % (same["name"], same["shortUrl"])
            elif dry_run:
                reply = "(dry-run) %s" % name
            else:
                who = m["author"].get("global_name") or m["author"]["username"]
                params = dict(name=name, idList=lists[conf.get("list", "Yapılacak")], pos="bottom",
                              key=cfg["trelloKey"], token=cfg["trelloToken"])
                if template:
                    params.update(idCardSource=template["id"], keepFromSource="checklists")
                if found_labels:
                    params["idLabels"] = ",".join(found_labels)
                me = next((t for t, d in people.items() if d == m["author"]["id"]), None)
                if me:
                    params["idMembers"] = me
                card = http_put("https://api.trello.com/1/cards?%s" % urllib.parse.urlencode(params), method="POST")
                desc = "**Prism asset:** Kategori/%s\n**Unity sahnesi:** Assets/Scenes/%s/\n\nDiscord'dan %s açtı." % (name, name, who)
                http_put("https://api.trello.com/1/cards/%s?%s" % (card["id"], urllib.parse.urlencode(
                    dict(desc=desc, key=cfg["trelloKey"], token=cfg["trelloToken"]))))
                cards.append({"name": name, "shortUrl": card["shortUrl"]})
                reply = "✅ **%s** kartı açıldı: %s\n%s" % (name, card["shortUrl"], "Kart sana atandı." if me else
                        "Kendini karta üye olarak ekle. (Bir kere `bağla <trello kullanıcı adın>` yazarsan bundan sonra kendiliğinden atanır.)")
        if reply and not dry_run:
            discord_bot(conf, "POST", "/channels/%s/messages" % channel,
                        {"content": reply, "message_reference": {"message_id": m["id"]}, "flags": SILENT,
                         "allowed_mentions": {"parse": [], "replied_user": False}})
        elif reply:
            print(reply)
        state["cardsLast"] = m["id"]
        if not dry_run:
            save_state(state)


def link_person(cfg, people, discord_id, args):
    """`bağla <trello username>`: notifications about that Trello member's cards go to this Discord user."""
    if len(args) != 1:
        return "Şöyle yaz: `bağla <trello kullanıcı adın>` (Trello'da profil resmine tıklayınca @ ile başlayan ad, @ olmadan)."
    wanted = args[0].lstrip("@").lower()
    members, on_board = {}, set()
    for board in cfg["boards"]:
        for mem in trello(cfg, "boards/%s/members" % board, fields="username,fullName"):
            members[mem["username"].lower()] = mem
            on_board.add(mem["id"])
    # Workspace members count too (read only): they can see the boards even before joining them.
    org = trello(cfg, "boards/%s" % next(iter(cfg["boards"])), fields="idOrganization").get("idOrganization")
    if org:
        for mem in trello(cfg, "organizations/%s/members" % org, fields="username,fullName"):
            members.setdefault(mem["username"].lower(), mem)
    mem = members.get(wanted)
    if not mem:
        return ("❌ Trello'da **%s** kullanıcı adında biri yok. Önce davetle Trello'ya katıl, "
                "sonra kullanıcı adını kontrol edip tekrar yaz." % wanted)
    join = "" if mem["id"] in on_board else (
        "\n⚠️ Henüz panolara üye değilsin; kartlar sana atanamaz. Trello'da **3D İşler** panosunu aç, "
        "sağ üstteki **Panoya katıl** düğmesine bas.")
    for t, d in list(people.items()):  # one Trello account per Discord user, and the other way round
        if d == discord_id or t == mem["id"]:
            people.pop(t)
    people[mem["id"]] = discord_id
    return ("🔗 Bağlandı: Trello'da **%s** = sen. Artık sana atanan kartlar, kartlarına gelen yorumlar ve taşımalar "
            "sana bildirim olarak gelecek." % mem["fullName"]) + join


# --- daily summary ---------------------------------------------------------------------------------

DONE_LISTS = ("Onaylandı", "Ana projeye hazır", "Tamamlandı")
STALE_DAYS = 3


def summary(force=False, dry_run=False):
    """Once a day after summary.time (weekdays), a short overview of every board in the summary channel."""
    cfg = load(CONFIG, None)
    conf = cfg.get("summary")
    if not conf:
        return
    state = load(STATE, {})
    now = datetime.datetime.now()
    today = now.date().isoformat()
    hour, minute = (int(x) for x in conf.get("time", "09:30").split(":"))
    if not force and (state.get("summaryDate") == today or now.weekday() >= 5 or (now.hour, now.minute) < (hour, minute)):
        return
    utc_now = datetime.datetime.now(datetime.timezone.utc)
    embeds = []
    for board in cfg["boards"]:
        info = trello(cfg, "boards/%s" % board, fields="name,url")
        names = {m["id"]: m["fullName"].split()[0] for m in trello(cfg, "boards/%s/members" % board, fields="fullName")}
        lists = trello(cfg, "boards/%s/lists" % board, fields="name")
        cards = [c for c in trello(cfg, "boards/%s/cards" % board, fields="name,idList,idMembers,dateLastActivity,isTemplate,shortUrl")
                 if not c.get("isTemplate")]
        lines, stale = [], []
        for l in lists:
            here = [c for c in cards if c["idList"] == l["id"]]
            if not here:
                continue
            if l["name"] in DONE_LISTS:
                lines.append("**%s** · %d kart" % (l["name"], len(here)))
                continue
            lines.append("**%s** · %d" % (l["name"], len(here)))
            for c in here[:10]:
                who = ", ".join(names.get(m, "?") for m in c["idMembers"]) or "atanmamış"
                lines.append("• [%s](%s) — %s" % (c["name"], c["shortUrl"], who))
                last = datetime.datetime.fromisoformat(c["dateLastActivity"].replace("Z", "+00:00"))
                if (utc_now - last).days >= STALE_DAYS:
                    stale.append("• [%s](%s) — %d gündür hareketsiz (*%s*)" % (c["name"], c["shortUrl"], (utc_now - last).days, l["name"]))
            if len(here) > 10:
                lines.append("• … ve %d kart daha" % (len(here) - 10))
        if stale:
            lines += ["", "⚠️ **Takılmış olabilir**"] + stale
        embeds.append({"title": info["name"], "url": info["url"], "color": 0x0079BF,
                       "description": "\n".join(lines)[:4000] or "Pano boş."})
    body = {"username": "Günlük Özet", "content": "☀️ **Günaydın! %s özeti**" % now.strftime("%d.%m.%Y"), "embeds": embeds[:10]}
    if dry_run:
        print(json.dumps(body, ensure_ascii=False, indent=1))
        return
    http(conf["webhook"], prepare(body))
    state = load(STATE, {})
    state["summaryDate"] = today
    save_state(state)


def hello():
    cfg = load(CONFIG, None)
    for board, hook in cfg["boards"].items():
        name = trello(cfg, "boards/%s" % board, fields="name")["name"]
        http(hook, {"username": "Trello", "embeds": [{
            "title": name, "url": "https://trello.com/b/%s" % board, "color": 0x0079BF,
            "description": "Bu kanal **%s** panosuna bağlandı. Kart açma, taşıma, yorum, atama, kontrol listesi ve "
                           "ek dosyalar buraya otomatik düşecek." % name}]})


if __name__ == "__main__":
    if sys.stdout is not None:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass
    try:
        dry = "--dry-run" in sys.argv
        if "--hello" in sys.argv:
            hello()
        elif "--summary" in sys.argv:
            summary(force=True, dry_run=dry)
        else:
            failed = False
            for job in (cards_run, run, prism_create_run, prism_run, summary):  # one failing (e.g. Trello down) does not stop the others
                try:
                    job(dry_run=dry)
                except Exception as exc:
                    log("%s error: %r" % (job.__name__, exc))
                    failed = True
            sys.exit(1 if failed else 0)
    except Exception as exc:  # pythonw has no console; keep a trace
        log("error: %r" % exc)
        raise
