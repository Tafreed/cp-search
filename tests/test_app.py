import time
from unittest.mock import MagicMock

import jwt

from website import app as flask_app, db
from website.models import Problem, SearchableMixin, User
from website import search as search_mod
from website.forms import RegistrationForm
from website.routes import paginate


# ---------- models ----------
def test_password_hashing(user):
    assert user.check_password("pw12345")
    assert not user.check_password("nope")


def test_avatar_and_repr(user, problem):
    assert user.avatar(32).startswith("https://www.gravatar.com/avatar/")
    assert "alice" in repr(user)
    assert "Two Sum" in repr(problem)


def test_mark_unmark(user, problem):
    assert not user.is_marked(problem)
    user.mark(problem)
    user.mark(problem)
    db.session.commit()
    assert user.is_marked(problem)
    assert user.marked_problems.count() == 1
    user.unmark(problem)
    user.unmark(problem)
    db.session.commit()
    assert not user.is_marked(problem)


def test_reset_token_roundtrip(user):
    token = user.get_reset_password_token()
    assert isinstance(token, str)
    assert User.verify_reset_password_token(token).id == user.id


def test_reset_token_invalid_and_expired(user):
    assert User.verify_reset_password_token("garbage") is None
    expired = jwt.encode({"reset_password": user.id, "exp": time.time() - 10},
                         flask_app.config["SECRET_KEY"], algorithm="HS256")
    assert User.verify_reset_password_token(expired) is None


def test_user_loader(user):
    from website.models import load_user
    assert load_user(str(user.id)).username == "alice"


# ---------- search ----------
def test_search_noop_without_elasticsearch(problem):
    flask_app.elasticsearch = None
    search_mod.add_to_index("problem", problem)
    search_mod.remove_from_index("problem", problem)
    assert search_mod.query_index("problem", "x", 1, 10) == ([], 0)
    results, total = Problem.search("x", 1, 10)
    assert total == 0 and results.all() == []


def test_search_with_elasticsearch(app, problem):
    es = MagicMock()
    es.search.return_value = {"hits": {"hits": [{"_id": str(problem.id)}], "total": {"value": 1}}}
    app.elasticsearch = es
    search_mod.add_to_index("problem", problem)
    es.index.assert_called_once_with(index="problem", id=problem.id, document={"keywords": "array"})
    search_mod.remove_from_index("problem", problem)
    es.delete.assert_called_once()
    assert search_mod.query_index("problem", "array", 2, 5) == ([problem.id], 1)
    results, total = Problem.search("array", 1, 10)
    assert total == 1 and [p.id for p in results.all()] == [problem.id]


def test_commit_hooks_index_changes(app):
    es = MagicMock()
    app.elasticsearch = es
    p = Problem(problem_name="A", problem_link="l1", keywords="k")
    db.session.add(p)
    db.session.commit()
    assert es.index.call_count == 1
    p.keywords = "k2"
    db.session.commit()
    assert es.index.call_count == 2
    db.session.delete(p)
    db.session.commit()
    assert es.delete.call_count == 1


def test_reindex(app, problem):
    es = MagicMock()
    app.elasticsearch = es
    Problem.reindex()
    assert es.index.call_count == 1


# ---------- routes ----------
def test_paginate():
    assert paginate(list(range(10)), 2, 3) == [3, 4, 5]
    assert paginate([], 1, 3) == []


def test_public_pages(client):
    for url in ("/", "/home", "/login", "/register", "/about"):
        assert client.get(url).status_code == 200


def test_home_search_redirects_to_about(client):
    r = client.post("/home", data={"query": "dp"})
    assert r.status_code == 302 and r.location.endswith("/about")
    r = client.post("/", data={"query": "dp"})
    assert r.status_code == 302


def test_register_and_login_flow(client):
    r = client.post("/register", data={"username": "bob", "email": "bob@example.com",
                                       "password": "pw", "password2": "pw"})
    assert r.status_code == 302 and r.location.endswith("/login")
    assert User.query.filter_by(username="bob").first() is not None

    bad = client.post("/login", data={"username": "bob", "password": "wrong"})
    assert bad.status_code == 302 and bad.location.endswith("/login")

    good = client.post("/login", data={"username": "bob", "password": "pw"})
    assert good.status_code == 302 and "/user/bob" in good.location


def test_register_rejects_duplicates(client, user):
    r = client.post("/register", data={"username": "alice", "email": "alice@example.com",
                                       "password": "pw", "password2": "pw"})
    assert r.status_code == 200
    assert User.query.count() == 1


def test_login_next_open_redirect_blocked(client, user):
    r = client.post("/login?next=http://evil.example/", data={"username": "alice", "password": "pw12345"})
    assert "evil.example" not in r.location
    client.get("/logout")
    r = client.post("/login?next=/about", data={"username": "alice", "password": "pw12345"})
    assert r.location.endswith("/about")


def test_authenticated_redirects(logged_in):
    for url in ("/", "/home", "/login"):
        r = logged_in.get(url)
        assert r.status_code == 302 and "/user/alice" in r.location


def test_login_required(client):
    assert client.get("/user/alice").status_code == 401 or client.get("/user/alice").status_code == 302


def test_user_page_and_search(logged_in):
    assert logged_in.get("/user/alice").status_code == 200
    r = logged_in.post("/user/alice", data={"query": "dp"})
    assert r.status_code == 302 and "/result/dp" in r.location


def test_result_page(logged_in, problem):
    assert logged_in.get("/user/alice/result/array").status_code == 200
    r = logged_in.post("/user/alice/result/array", data={"query": "graph"})
    assert r.status_code == 302 and "/result/graph" in r.location


def test_result_pagination_links(logged_in, app, problem):
    es = MagicMock()
    es.search.return_value = {"hits": {"hits": [{"_id": str(problem.id)}], "total": {"value": 100}}}
    app.elasticsearch = es
    r = logged_in.get("/user/alice/result/x?page=2")
    assert r.status_code == 200
    assert b"page=3" in r.data or b"page=1" in r.data


def test_mark_and_unmark_routes(logged_in, user, problem):
    r = logged_in.post(f"/mark/{problem.id}", headers={"Referer": "/user/alice"})
    assert r.status_code == 302
    assert user.is_marked(problem)
    assert logged_in.get("/user/alice/marked_problems").status_code == 200
    r = logged_in.post(f"/unmark/{problem.id}", headers={"Referer": "/user/alice"})
    assert r.status_code == 302
    assert not user.is_marked(problem)


def test_logout(logged_in):
    r = logged_in.get("/logout")
    assert r.status_code == 302 and r.location.endswith("/home")


def test_unknown_user_marked_problems_404(logged_in):
    assert logged_in.get("/user/ghost/marked_problems").status_code == 404


# ---------- forms ----------
def test_registration_form_duplicate(app, user):
    with app.test_request_context(method="POST", data={"username": "alice", "email": "x@example.com",
                                                      "password": "a", "password2": "a"}):
        form = RegistrationForm()
        assert not form.validate()
        assert "username" in form.errors


def test_registration_form_duplicate_email(app, user):
    with app.test_request_context(method="POST", data={"username": "zed", "email": "alice@example.com",
                                                      "password": "a", "password2": "a"}):
        form = RegistrationForm()
        assert not form.validate()
        assert "email" in form.errors


# ---------- email ----------
def test_send_email_dispatches(app, monkeypatch):
    import website.emaail as em
    sent = []
    monkeypatch.setattr(em.mail, "send", lambda msg: sent.append(msg))

    class ImmediateThread:
        def __init__(self, target, args):
            self.target, self.args = target, args
        def start(self):
            self.target(*self.args)

    monkeypatch.setattr(em, "Thread", ImmediateThread)
    em.send_email("subj", "a@example.com", ["b@example.com"], "text", "<p>html</p>")
    assert sent and sent[0].subject == "subj"


def test_send_password_reset_email(app, user, monkeypatch):
    import website.emaail as em
    captured = {}
    monkeypatch.setattr(em, "render_template", lambda name, **kw: name)
    monkeypatch.setattr(em, "send_email", lambda *a, **kw: captured.update(args=a, kw=kw))
    em.send_password_reset_email(user)
    assert captured["kw"]["recipients"] == ["alice@example.com"]
