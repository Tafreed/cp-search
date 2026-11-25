import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret"

import pytest

from website import app as flask_app, db
from website.models import Problem, User


@pytest.fixture()
def app():
    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SERVER_NAME="localhost",
        MAIL_SUPPRESS_SEND=True,
    )
    flask_app.elasticsearch = None
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def user(app):
    u = User(username="alice", email="alice@example.com")
    u.set_password("pw12345")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture()
def problem(app):
    p = Problem(problem_name="Two Sum", problem_link="http://x/1", keywords="array", tags="easy", platform="lc")
    db.session.add(p)
    db.session.commit()
    return p


@pytest.fixture()
def logged_in(client, user):
    client.post("/login", data={"username": "alice", "password": "pw12345"})
    return client
