# Utiliser une image Ubuntu
FROM ubuntu:24.04

# Installer Python 3.12, cron et curl
RUN apt-get update && apt-get install -y python3.12 python3-pip curl cron

# Installer uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Définir le dossier de travail
WORKDIR /app

# Copier les fichiers nécessaires
COPY pyproject.toml /app/
COPY edoc_retriever.py /app/

# Installer les dépendances avec uv (en forçant pip)
# RUN uv venv .venv && .venv/bin/python -m pip install .

# Ajouter une tâche cron pour exécuter le script tous les jours à 2h du matin
RUN echo "1 * * * * root /app/.venv/bin/python /app/edoc_retriever.py >> /var/log/cron.log 2>&1" > /etc/cron.d/edoc-cron

# Appliquer les permissions et activer cron
RUN chmod 0644 /etc/cron.d/edoc-cron && crontab /etc/cron.d/edoc-cron

# Démarrer le service cron en arrière-plan
CMD cron -f
