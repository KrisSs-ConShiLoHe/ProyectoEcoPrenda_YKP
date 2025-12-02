# db_routers.py

class AppRouter:
    """
    Un router para controlar operaciones de BD para la app inventario.
    """
    def db_for_read(self, model, **hints):
        if model._meta.app_label == 'A_EcoPrenda':
            return 'mysql_db'
        return 'default'
    # ... implementa db_for_write, allow_relation, allow_migrate de forma similar
