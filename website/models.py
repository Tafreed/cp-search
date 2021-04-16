from datetime import datetime
from hashlib import md5
from time import time
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
from website import app, db, login
import jellyfish
from website.search import add_to_index, remove_from_index, query_index


class SearchableMixin(object):
    @classmethod
    def search(cls, expression, page, per_page):
        ids, total = query_index(cls.__tablename__, expression, page, per_page)
        if total == 0:
            return cls.query.filter_by(id=0), 0
        when = []
        for i in range(len(ids)):
            when.append((ids[i], i))
        print(cls.query.filter(cls.id.in_(ids)))
        return cls.query.filter(cls.id.in_(ids)).order_by(
            db.case(when, value=cls.id)), total

    @classmethod
    def before_commit(cls, session):
        session._changes = {
            'add': list(session.new),
            'update': list(session.dirty),
            'delete': list(session.deleted)
        }

    @classmethod
    def after_commit(cls, session):
        for obj in session._changes['add']:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes['update']:
            if isinstance(obj, SearchableMixin):
                add_to_index(obj.__tablename__, obj)
        for obj in session._changes['delete']:
            if isinstance(obj, SearchableMixin):
                remove_from_index(obj.__tablename__, obj)
        session._changes = None

    @classmethod
    def reindex(cls):
        for obj in cls.query:
            add_to_index(cls.__tablename__, obj)

db.event.listen(db.session, 'before_commit', SearchableMixin.before_commit)
db.event.listen(db.session, 'after_commit', SearchableMixin.after_commit)

marked = db.Table(
    'marked',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('problem_id', db.Integer, db.ForeignKey('problem.id'))
)

class Problem(SearchableMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    problem_name = db.Column(db.String(64), index=True)
    problem_link = db.Column(db.String(64), index=True, unique=True)
    keywords = db.Column(db.String(140), index=True)
    tags = db.Column(db.String(140), index=True)
    platform = db.Column(db.String(140), index=True)
    __searchable__ = ['keywords']


    def __repr__(self):
        return '<Problem {}>'.format(self.problem_name) 



class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))

    marked_problems = db.relationship(
        'Problem', secondary=marked,
        primaryjoin=(marked.c.user_id==id),
        secondaryjoin="marked.c.problem_id==Problem.id",
        backref=db.backref('markers', lazy='dynamic'), lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def avatar(self, size):
        digest = md5(self.email.lower().encode('utf-8')).hexdigest()
        return 'https://www.gravatar.com/avatar/{}?d=identicon&s={}'.format(
            digest, size)

    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            app.config['SECRET_KEY'], algorithm='HS256').decode('utf-8')

    def is_marked(self, problem):
        return self.marked_problems.filter(marked.c.problem_id == problem.id).count() > 0

    def mark(self, problem):
        if not self.is_marked(problem):
            self.marked_problems.append(problem)

    def unmark(self, problem):
        if self.is_marked(problem):
            self.marked_problems.remove(problem)

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, app.config['SECRET_KEY'],
                            algorithms=['HS256'])['reset_password']
        except:
            return
        return User.query.get(id)

    def __repr__(self):
        return '<User {}>'.format(self.username)    


@login.user_loader
def load_user(id):
    return User.query.get(int(id))






