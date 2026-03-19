"""
FridgeFriend — Flask galvenais fails
Visas routes izmanto OOP modeļus no models.py
"""
import os
import secrets
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, flash)
from models import (Database, UserModel, RecipeModel, CommentModel,
                    LikeModel, FavoriteModel, FridgeModel, IngredientModel,
                    PasswordUtils, UPLOAD_FOLDER, ALLOWED_EXTENSIONS)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

users     = UserModel()
recipes   = RecipeModel()
comments  = CommentModel()
likes     = LikeModel()
favorites = FavoriteModel()
fridge    = FridgeModel()
ings      = IngredientModel()

def get_current_user():
    if 'user_id' in session:
        return users.get_by_id(session['user_id'])
    return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_current_user():
            flash('Lūdzu pieslēdzies.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user or not user['is_admin']:
            flash('Nav administratora piekļuves tiesību.', 'danger')
            return redirect(url_for('sakums'))
        return f(*args, **kwargs)
    return decorated

@app.context_processor
def inject_user():
    return dict(current_user=get_current_user())

# ── publiskais ──
@app.route('/')
def sakums():
    popular = recipes.get_popular(3)
    return render_template('sakums.html', recipes=popular)

@app.route('/sastavdalas')
def sastavdalas():
    return render_template('sastavdalas.html', by_cat=ings.get_all_by_category())

@app.route('/receptes', methods=['GET', 'POST'])
def receptes():
    selected = request.form.getlist('ingredients') if request.method == 'POST' else []
    results = recipes.search_by_ingredients(selected)
    return render_template('receptes.html', results=results, selected=selected)

@app.route('/recepte/<int:recipe_id>')
def recepte(recipe_id):
    recipe = recipes.get_by_id(recipe_id)
    if not recipe:
        flash('Recepte nav atrasta.', 'danger')
        return redirect(url_for('receptes'))
    user = get_current_user()
    return render_template('recepte.html',
        recipe=recipe,
        steps=recipes.get_steps(recipe_id),
        ingredients=recipes.get_ingredients(recipe_id),
        recipe_comments=comments.get_for_recipe(recipe_id),
        selected=request.args.get('selected', '').split(','),
        user_liked=likes.user_liked(user['id'], recipe_id) if user else False,
        user_faved=favorites.is_favorite(user['id'], recipe_id) if user else False,
        like_count=likes.count(recipe_id))

@app.route('/mann-nav')
def mann_nav():
    cheap = sorted(recipes.get_all_public(), key=lambda r: r['cost_eur'])[:3]
    return render_template('mannav.html', cheap_recipes=cheap)

# ── ledusskapis ──
@app.route('/mans-ledusskapis')
def mans_ledusskapis():
    user = get_current_user()
    items = fridge.get_user_items(user['id']) if user else []
    return render_template('mansledusskapis.html', fridge_items=items)

@app.route('/mans-ledusskapis/pievienot', methods=['POST'])
@login_required
def add_fridge_item():
    fridge.add(session['user_id'], request.form.get('name','').strip(),
               request.form.get('emoji','🛒'), request.form.get('expiry') or None)
    return redirect(url_for('mans_ledusskapis'))

@app.route('/mans-ledusskapis/dzest/<int:item_id>', methods=['POST'])
@login_required
def delete_fridge_item(item_id):
    fridge.delete(item_id, session['user_id'])
    return redirect(url_for('mans_ledusskapis'))

# ── patikumi un izlase ──
@app.route('/recepte/<int:recipe_id>/patik', methods=['POST'])
@login_required
def toggle_like(recipe_id):
    liked = likes.toggle(session['user_id'], recipe_id)
    count = likes.count(recipe_id)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'liked': liked, 'count': count})
    return redirect(url_for('recepte', recipe_id=recipe_id))

@app.route('/recepte/<int:recipe_id>/izlase', methods=['POST'])
@login_required
def toggle_favorite(recipe_id):
    faved = favorites.toggle(session['user_id'], recipe_id)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'faved': faved})
    return redirect(url_for('recepte', recipe_id=recipe_id))

@app.route('/izlase')
@login_required
def izlase():
    return render_template('izlase.html', favorites=favorites.get_user_favorites(session['user_id']))

# komentari 
@app.route('/recepte/<int:recipe_id>/komentars', methods=['POST'])
@login_required
def add_comment(recipe_id):
    content = request.form.get('content','').strip()
    if content:
        comments.add(session['user_id'], recipe_id, content)
    return redirect(url_for('recepte', recipe_id=recipe_id) + '#comments')

@app.route('/komentars/<int:comment_id>/dzest', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = comments.get_by_id(comment_id)
    user = get_current_user()
    if comment and (comment['user_id'] == user['id'] or user['is_admin']):
        recipe_id = comment['recipe_id']
        comments.delete(comment_id)
        return redirect(url_for('recepte', recipe_id=recipe_id) + '#comments')
    flash('Nav atļauts.', 'danger')
    return redirect(url_for('sakums'))

# lietotaju receptes
@app.route('/manas-receptes')
@login_required
def manas_receptes():
    return render_template('manas_receptes.html', my_recipes=recipes.get_by_user(session['user_id']))

def _save_recipe_form(recipe_id):
    recipes.clear_ingredients(recipe_id)
    recipes.clear_steps(recipe_id)

    for name, emoji, amount in zip(
        request.form.getlist('ing_name[]'),
        request.form.getlist('ing_emoji[]'),
        request.form.getlist('ing_amount[]'),
    ):
        if name.strip():
            recipes.add_ingredient(recipe_id, name.strip(), emoji or '🍴', amount.strip())

    for step_num, desc in enumerate(request.form.getlist('step_desc[]'), 1):
        if desc.strip():
            recipes.add_step(recipe_id, step_num, desc.strip())

@app.route('/izveidot-recepti', methods=['GET', 'POST'])
@login_required
def izveidot_recepti():
    if request.method == 'POST':
        recipe_id = recipes.create(
            name=request.form['name'], emoji=request.form.get('emoji','🍽️'),
            time_minutes=int(request.form.get('time_minutes',15)),
            cost_eur=float(request.form.get('cost_eur',1.0)),
            difficulty=request.form.get('difficulty','Viegli'),
            serves=request.form.get('serves','1 porcija'),
            tip=request.form.get('tip',''), description=request.form.get('description',''),
            created_by=session['user_id'], is_official=0, is_public=0)
        _save_recipe_form(recipe_id)
        flash('Recepte izveidota! Redzama pēc administratora apstiprināšanas.', 'success')
        return redirect(url_for('manas_receptes'))
    return render_template('izveidot_recepti.html')

@app.route('/recepte/<int:recipe_id>/rediget', methods=['GET', 'POST'])
@login_required
def rediget_recepti(recipe_id):
    recipe = recipes.get_by_id(recipe_id)
    user = get_current_user()
    if not recipe or (recipe['created_by'] != user['id'] and not user['is_admin']):
        flash('Nav atļauts.', 'danger')
        return redirect(url_for('sakums'))
    if request.method == 'POST':
        recipes.update(recipe_id,
            name=request.form['name'], emoji=request.form.get('emoji','🍽️'),
            time_minutes=int(request.form.get('time_minutes',15)),
            cost_eur=float(request.form.get('cost_eur',1.0)),
            difficulty=request.form.get('difficulty','Viegli'),
            serves=request.form.get('serves','1 porcija'),
            tip=request.form.get('tip',''), description=request.form.get('description',''))
        _save_recipe_form(recipe_id)
        flash('Recepte atjaunināta!', 'success')
        return redirect(url_for('recepte', recipe_id=recipe_id))
    return render_template('izveidot_recepti.html', recipe=recipe,
                           r_ings=recipes.get_ingredients(recipe_id),
                           r_steps=recipes.get_steps(recipe_id))

@app.route('/recepte/<int:recipe_id>/dzest', methods=['POST'])
@login_required
def dzest_recepti(recipe_id):
    recipe = recipes.get_by_id(recipe_id)
    user = get_current_user()
    if recipe and (recipe['created_by'] == user['id'] or user['is_admin']):
        recipes.delete(recipe_id)
        flash('Recepte dzēsta.', 'success')
    return redirect(url_for('manas_receptes'))

# profils 
@app.route('/profils', methods=['GET', 'POST'])
@login_required
def profils():
    user = get_current_user()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'profile':
            ok = users.update_profile(user['id'],
                request.form.get('display_name','').strip(),
                request.form.get('bio','').strip(),
                request.form.get('username','').strip(),
                request.form.get('email','').strip())
            flash('Profils atjaunināts!' if ok else 'Lietotājvārds vai e-pasts aizņemts.', 'success' if ok else 'danger')
        elif action == 'password':
            curr = request.form.get('current_password','')
            new_pw = request.form.get('new_password','')
            if PasswordUtils.verify(curr, user['password_hash']):
                users.update_password(user['id'], new_pw)
                flash('Parole mainīta!', 'success')
            else:
                flash('Nepareiza pašreizējā parole.', 'danger')
        elif action == 'avatar':
            f = request.files.get('avatar')
            if f and f.filename and allowed_file(f.filename):
                ext = f.filename.rsplit('.', 1)[1].lower()
                fname = f'user_{user["id"]}.{ext}'
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fname))
                users.update_avatar(user['id'], fname)
                flash('Profila attēls atjaunināts!', 'success')
            else:
                flash('Nederīgs fails.', 'danger')
        return redirect(url_for('profils'))
    return render_template('profils.html', user=user)

@app.route('/lietotajs/<username>')
def publiskais_profils(username):
    profile_user = users.get_by_username(username)
    if not profile_user:
        flash('Lietotājs nav atrasts.', 'danger')
        return redirect(url_for('sakums'))
    user_recipes = [r for r in recipes.get_by_user(profile_user['id']) if r['is_public']]
    return render_template('publiskais_profils.html', profile_user=profile_user, user_recipes=user_recipes)

# admins 
@app.route('/admin')
@admin_required
def admin_index():
    return render_template('admin/index.html',
        all_users=users.get_all(), pending=recipes.get_pending_review(),
        all_recipes=recipes.get_all_public(), all_comments=comments.get_all(),
        all_ings=ings.get_all())

@app.route('/admin/recepte/publicet/<int:recipe_id>', methods=['POST'])
@admin_required
def admin_publicet(recipe_id):
    recipes.publish(recipe_id)
    flash('Recepte publicēta!', 'success')
    return redirect(url_for('admin_index') + '#pending')

@app.route('/admin/recepte/dzest/<int:recipe_id>', methods=['POST'])
@admin_required
def admin_dzest_recepti(recipe_id):
    recipes.delete(recipe_id)
    flash('Recepte dzēsta.', 'success')
    return redirect(url_for('admin_index') + '#recipes')

@app.route('/admin/komentars/dzest/<int:comment_id>', methods=['POST'])
@admin_required
def admin_dzest_komentaru(comment_id):
    comments.delete(comment_id)
    flash('Komentārs dzēsts.', 'success')
    return redirect(url_for('admin_index') + '#comments')

@app.route('/admin/lietotajs/dzest/<int:user_id>', methods=['POST'])
@admin_required
def admin_dzest_lietotaju(user_id):
    if user_id == session['user_id']:
        flash('Nevar dzēst savu kontu!', 'danger')
    else:
        users.delete(user_id)
        flash('Lietotājs dzēsts.', 'success')
    return redirect(url_for('admin_index') + '#users')

@app.route('/admin/sastavdala/pievienot', methods=['POST'])
@admin_required
def admin_add_ingredient():
    ings.create(request.form.get('name','').strip(),
                request.form.get('emoji','🥬'),
                request.form.get('category','Cits'))
    flash('Sastāvdaļa pievienota!', 'success')
    return redirect(url_for('admin_index') + '#ingredients')

@app.route('/admin/sastavdala/dzest/<int:ing_id>', methods=['POST'])
@admin_required
def admin_dzest_sastavdalu(ing_id):
    ings.delete(ing_id)
    flash('Sastāvdaļa dzēsta.', 'success')
    return redirect(url_for('admin_index') + '#ingredients')

@app.route('/admin/jauna-recepte', methods=['GET', 'POST'])
@admin_required
def admin_jauna_recepte():
    if request.method == 'POST':
        rid = recipes.create(
            name=request.form['name'], emoji=request.form.get('emoji','🍽️'),
            time_minutes=int(request.form.get('time_minutes',15)),
            cost_eur=float(request.form.get('cost_eur',1.0)),
            difficulty=request.form.get('difficulty','Viegli'),
            serves=request.form.get('serves','1 porcija'),
            tip=request.form.get('tip',''), description=request.form.get('description',''),
            created_by=session['user_id'], is_official=1, is_public=1)
        _save_recipe_form(rid)
        flash('Recepte izveidota!', 'success')
        return redirect(url_for('admin_index') + '#recipes')
    return render_template('izveidot_recepti.html', admin_mode=True)

# autorizacija 
@app.route('/pieslegt', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = users.authenticate(request.form['email'], request.form['password'])
        if user:
            session['user_id'] = user['id']
            flash(f'Laipni lūgts, {user["display_name"] or user["username"]}!', 'success')
            return redirect(url_for('sakums'))
        flash('Nepareizs e-pasts vai parole.', 'danger')
    return render_template('login.html')

@app.route('/registreties', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        uid = users.create(request.form['username'], request.form['email'], request.form['password'])
        if uid:
            session['user_id'] = uid
            flash('Konts izveidots!', 'success')
            return redirect(url_for('sakums'))
        flash('Lietotājvārds vai e-pasts jau eksistē.', 'danger')
    return render_template('register.html')

@app.route('/iziet')
def logout():
    session.clear()
    return redirect(url_for('sakums'))

# API
@app.route('/api/generate-password')
def api_generate_password():
    length = max(12, min(32, int(request.args.get('length', 16))))
    return jsonify({'password': PasswordUtils.generate(length)})

@app.route('/api/hash-password', methods=['POST'])
def api_hash_password():
    data = request.get_json() or {}
    pw = data.get('password', '')
    if not pw:
        return jsonify({'error': 'Nav paroles'}), 400
    return jsonify({'hash': PasswordUtils.hash(pw), 'algorithm': 'pbkdf2:sha256:600000'})

@app.route('/api/receptes')
def api_receptes():
    return jsonify([dict(r) for r in recipes.get_all_public()])

@app.route('/api/ledusskapis')
def api_ledusskapis():
    user = get_current_user()
    if not user:
        return jsonify({'error': 'Nav autentificēts'}), 401
    return jsonify([dict(i) for i in fridge.get_user_items(user['id'])])

if __name__ == '__main__':
    db = Database.get()
    db.init_schema()
    app.run(debug=True, port=5000)
