from models import User, db


def register_user(email, password):
    """Crea una cuenta nueva; devuelve (user, error) — error es un string si el correo ya existe."""
    email = email.strip().lower()
    if User.query.filter_by(email=email).first():
        return None, "Ya existe una cuenta con ese correo."
    user = User(email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user, None


def authenticate(email, password):
    """Verifica email + contraseña; devuelve el User si son correctos, None si no."""
    user = User.query.filter_by(email=email.strip().lower()).first()
    if user and user.check_password(password):
        return user
    return None
