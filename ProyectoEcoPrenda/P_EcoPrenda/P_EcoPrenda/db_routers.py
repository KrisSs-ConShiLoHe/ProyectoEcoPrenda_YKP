# db_routers.py

class AppRouter:
    """
    Un router para controlar operaciones de BD para la app A_EcoPrenda.
    """
    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'A_EcoPrenda':
            return 'mysql_db'
        return 'default'

    def db_for_write(self, model, **hints):
        if model._meta.app_label == 'A_EcoPrenda':
            return 'mysql_db'
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        # Permitir relaciones entre objetos de la misma base de datos
        if obj1._meta.app_label == 'A_EcoPrenda' and obj2._meta.app_label == 'A_EcoPrenda':
            return True
        if obj1._meta.app_label != 'A_EcoPrenda' and obj2._meta.app_label != 'A_EcoPrenda':
            return True
        return False

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in ['A_EcoPrenda', 'auth', 'contenttypes', 'sessions', 'admin']:
            return db == 'mysql_db'
        return db == 'default'
