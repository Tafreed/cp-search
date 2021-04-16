from datetime import datetime
from flask import render_template, flash, redirect, url_for, request
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.urls import url_parse
from website import app, db
from website.forms import LoginForm, RegistrationForm, EditProfileForm, \
    EmptyForm, PostForm, ResetPasswordRequestForm, ResetPasswordForm, SearchForm
from website.models import User, Problem
from website.emaail import send_password_reset_email
import math


def paginate(lst, page_no, items_per_page):
    res = []
    for i in range((page_no-1)*items_per_page, min(page_no*items_per_page, len(lst))):
        res.append(lst[i])
    return res


@app.route('/', methods=['GET', 'POST'])
@app.route('/home', methods=['GET', 'POST'])
def home():
    if current_user.is_authenticated:
        return redirect(url_for('user',username=current_user.username))
    form = SearchForm()
    if form.validate_on_submit():
        return redirect(url_for('about'))

    return render_template('home.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('user',username=current_user.username))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('login'))
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('user',username=current_user.username)
        return redirect(next_page)
    return render_template('login.html', title='Sign In', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)


@app.route('/reset_password_request', methods=['GET', 'POST'])
def reset_password_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = ResetPasswordRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            send_password_reset_email(user)
        flash('Check your email for the instructions to reset your password')
        return redirect(url_for('login'))
    return render_template('reset_password_request.html', title='Reset Password', form=form)


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_password_token(token)
    if not user:
        return redirect(url_for('index'))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset.')
        return redirect(url_for('login'))
    return render_template('reset_password.html', form=form)


@app.route('/user/<username>', methods=['GET', 'POST'])
@login_required
def user(username):
    user = User.query.filter_by(username=username).first()
    form = SearchForm()
    if form.validate_on_submit():
        query = form.query.data
        return redirect(url_for('result', username=username, query=query))

    return render_template('user.html', user=user, form=form)


@app.route('/user/<username>/result/<query>', methods=['GET', 'POST'])
@login_required
def result(username, query):
    problems_per_page = app.config['POSTS_PER_PAGE']

    form = SearchForm()
    user = User.query.filter_by(username=username).first()
    q = query

    if form.validate_on_submit():
        q = form.query.data
        return redirect(url_for('result', username=username, query=q))

    cur_page = request.args.get('page', 1, type=int)
    problems_, total = Problem.search(q, cur_page, problems_per_page)
    problems = problems_.all()
    last_page = math.ceil(len(problems) / problems_per_page)
    
    next_url = url_for('result', username=user.username, page=cur_page+1, query=q) \
        if total > cur_page * problems_per_page else None

    prev_url = url_for('result', username=user.username, page=cur_page-1, query=q) \
        if cur_page > 1 else None
    return render_template('user_result.html', user=user, form=form, problems=problems, next_url=next_url, prev_url=prev_url)


@app.route('/user/<username>/marked_problems')
@login_required
def marked_problems(username):
    user = User.query.filter_by(username=username).first_or_404()
    problems = user.marked_problems.all()
    form = EmptyForm()
    return render_template('marked_problems.html', user=user, problems=problems, form=form)


@app.route('/mark/<prob_id>', methods=['POST'])
@login_required
def mark_problem(prob_id):
    form = EmptyForm()
    if form.validate_on_submit():
        problem = Problem.query.filter_by(id=prob_id).first()
        if problem is None:
            flash('Problem {} not found.'.format(prob_id))
            redirect(url_for('user', username=current_user.username))
        current_user.mark(problem)
        db.session.commit()
        return redirect(request.referrer)
    else:
        return redirect(url_for('home'))


@app.route('/unmark/<prob_id>', methods=['POST'])
@login_required
def unmark_problem(prob_id):
    form = EmptyForm()
    if form.validate_on_submit():
        problem = Problem.query.filter_by(id=prob_id).first()
        if problem is None:
            flash('Problem {} not found.'.format(prob_id))
            redirect(url_for('user', username=current_user.username))
        current_user.unmark(problem)
        db.session.commit()
        return redirect(request.referrer)
    else:
        return redirect(url_for('home'))


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/about')
def about():
    return render_template('about.html')

