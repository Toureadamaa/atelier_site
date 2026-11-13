# Ателье — application Django + SQL Server

Implémentation du rapport « Проектирование базы данных швейного ателье » —
Туре А. А., groupe ИДБ-24-07, МГТУ «СТАНКИН».
L'interface est en russe (comme le rapport), les explications ci-dessous sont en français.

| Dossier | Contenu |
|---|---|
| `atelier/`, `config/`, `manage.py` | application web Django |
| [`sql/ogranicheniya_p3_3.sql`](sql/ogranicheniya_p3_3.sql) | les 26 contraintes du § 3.3 (CHECK, UNIQUE, NOT NULL, triggers) |
| [`docs/ogranicheniya.md`](docs/ogranicheniya.md) | chaque contrainte suivie de son code SQL |

## 1. Prérequis (Windows)

- **Python 3.10+** — https://www.python.org (cocher « Add Python to PATH »)
- **SQL Server** (Express suffit) + **SSMS**
- **Microsoft ODBC Driver 17 ou 18 for SQL Server** (souvent déjà installé avec SQL Server).
  Pour vérifier : menu Démarrer → « Sources de données ODBC (64 bits) » → onglet *Pilotes*.

## 2. Installation

Dans PowerShell, depuis le dossier du projet :

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Base de données utilisée : `projet corse` (vos tables existantes)

L'application travaille directement sur vos 12 tables (Клиент, Заказ, … avec les colonnes
Номер_клиента, Номер_заказа, …). Connexion par défaut : serveur `DESKTOP-7VAOGUU\SQLEXPRESS`,
base `projet corse`, authentification Windows, pilote ODBC 17.
Pour changer : `$env:DB_HOST = "..."`, `$env:DB_NAME = "..."`, `$env:DB_DRIVER = "ODBC Driver 18 for SQL Server"`.

**Conseil : faites d'abord une sauvegarde** de `projet corse` dans SSMS (clic droit → Tâches → Sauvegarder).

## 4. Lancer

```powershell
python manage.py migrate        # tables système Django + colonnes ajoutées à vos tables
python manage.py proverit_bd    # vérifie que les 12 tables correspondent au code
python manage.py zapolnit       # rôles et comptes ; données de test seulement si Клиент est vide
python manage.py runserver
```

Ouvrir http://127.0.0.1:8000

`migrate` **ne supprime rien** : il ajoute les tables Django (auth_user, django_session…) et
quelques colonnes à vos tables (voir plus bas). `zapolnit` lie le compte `klient` au premier client
existant et `master` / `zakroishik` aux deux maîtres les plus expérimentés.

### Comptes de test

| Rôle | Login | Mot de passe | Pages |
|---|---|---|---|
| Управляющий | `upravlyayushii` | `upr12345` | panneau, toutes les commandes, tâches, stock, achats, modèles, maîtres |
| Агент приёма | `agent` | `agent12345` | clients, mesures, commandes, rendez-vous, essayages |
| Мастер | `master` | `master12345` | mes tâches (changer le statut, signaler un problème), mes essayages |
| Клиент | `klient` | `klient12345` | catalogue, mes commandes, mes rendez-vous et essayages |
| Admin Django | `admin` | `admin` | http://127.0.0.1:8000/admin/ |

Test rapide sans SQL Server : `$env:DB_ENGINE="sqlite"`, puis `python manage.py migrate --run-syncdb` et les autres commandes.
Tests automatiques (sur SQLite) : `$env:DB_ENGINE="sqlite"` puis `python manage.py test atelier` (32 tests).

## 4 bis. Ouvrir l'application sur un téléphone

L'interface est adaptée aux écrans de téléphone (menu latéral repliable, tableaux allégés).

**Téléphone sur le même Wi-Fi que le PC**

1. Lancer l'application : `python manage.py runserver 0.0.0.0:8000`.
2. Trouver l'adresse IP du PC : `ipconfig` → carte « Wi-Fi » → **Adresse IPv4** (par ex. `192.168.1.23`).
3. Autoriser le port dans le pare-feu (PowerShell **administrateur**, une seule fois) :
   ```powershell
   New-NetFirewallRule -DisplayName "Atelier 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
   ```
4. Sur le téléphone, connecté au **même Wi-Fi** : ouvrir `http://192.168.1.23:8000`.

Les réseaux publics ou universitaires bloquent souvent les échanges entre appareils.

**Icône sur l'écran d'accueil** : dans le navigateur du téléphone, menu → « Ajouter à l'écran d'accueil »
(Android/Chrome) ou Partager → « Sur l'écran d'accueil » (iPhone/Safari). L'Atelier s'ouvre alors
comme une application, en plein écran, avec sa propre icône.

## 4 ter. Contraintes du § 3.3 : vérifiées par SQL Server

Les 26 règles sont créées dans la base `projet corse` par le script
[`sql/ogranicheniya_p3_3.sql`](sql/ogranicheniya_p3_3.sql) (à exécuter dans SSMS) :
contraintes `CHECK`, `UNIQUE`, `NOT NULL` et triggers.

Réglage `PROVERKA_V_BAZE` dans `config/settings.py` :

- **True** (par défaut avec SQL Server) : Django ne vérifie pas ces règles lui-même. Il envoie les données
  à la base ; si une contrainte ou un trigger refuse, la transaction est annulée et le message de SQL Server
  s'affiche au-dessus du formulaire : « База данных отклонила изменение: … ».
  Si un trigger affiche un texte (`print` ou `raiserror`), c'est ce texte qui est montré.
- **False** : Django vérifie aussi les règles avant d'écrire (`clean()`, `Meta.constraints`).
  Sans modifier le code : `$env:PROVERKA_V_BAZE="0"` avant `python manage.py runserver`.

Quand les triggers de stock existent (`tr_позициязаказа_списание`, `tr_позициязакупки_поступление`),
l'application ne modifie pas le stock elle-même : c'est la base qui le fait.

## 5. Design : HTML, CSS et JavaScript sans bibliothèque

L'interface n'utilise aucun framework CSS ni bibliothèque JavaScript (pas de Bootstrap, pas de jQuery).

- `atelier/static/atelier/css/atelier.css` : toute la charte graphique (variables de couleurs, typographie,
  grille de mise en page, composants, version mobile). Idée : un magazine de mode posé sur une table de coupe —
  papier quadrillé, craie de tailleur rouge, ruban métrique jaune, tapis de coupe vert.
- `atelier/static/atelier/js/atelier.js` : menu mobile, messages qui se ferment seuls, lignes de tableau cliquables,
  compteurs animés du tableau de bord, affichage du mot de passe, remplissage des comptes de test,
  confirmation avant d'annuler un rendez-vous.
- `atelier/static/atelier/fonts/` : polices Prata (titres), Onest (texte) et JetBrains Mono (étiquettes),
  incluses localement avec l'alphabet cyrillique — le site fonctionne sans Internet.

Aucune étape de compilation n'est nécessaire : il suffit de lancer `python manage.py runserver`.

## 6. Correspondance rapport ↔ code

| Таблица SQL Server | Модель Django | Ключ |
|---|---|---|
| Клиент | `Klient` | Номер_клиента |
| Заказ | `Zakaz` | Номер_заказа |
| Запись | `Zapis` | Номер_записи |
| Модель | `Model` | Номер_модели |
| Мерки | `Merki` | Номер_мерки |
| Мастер | `Master` | Номер_мастера |
| Задача | `Zadacha` | Номер_задачи |
| График_примерок | `Primerka` | Номер_примерки |
| Материал | `Material` | Номер_материала |
| Закупка | `Zakupka` | Номер_закупки |
| Позиция_закупки | `PoziciyaZakupki` | (Номер_закупки, Номер_материала) — clé composée |
| Позиция_заказа | `PoziciyaZakaza` | (Номер_заказа, Номер_материала) — clé composée |

Chaque champ Django indique sa colonne avec `db_column="..."` et chaque modèle sa table avec
`db_table="..."` ; `managed = False` signifie que Django n'a pas créé ces tables et n'y touche pas.

### Où sont les contraintes du chapitre 3.3

- **Dans la base** (visibles dans SSMS, dossiers *Ключи*, *Ограничения*, *Триггеры* de chaque table) :
  toutes les règles, créées par `sql/ogranicheniya_p3_3.sql`.
- **Dans le code** (`atelier/models.py`) : les mêmes règles en `clean()` / `Meta.constraints`, utilisées
  seulement si `PROVERKA_V_BAZE = False` (et pour les tests sur SQLite).

### Colonnes ajoutées à vos tables par `migrate` (à signaler dans le rapport)

1. `Заказ.Статус` : nécessaire pour « suivre l'état de la commande » et pour la limite de 2 commandes actives.
2. `Задача.Статус`, `Сложная`, `Комментарий` : le maître met à jour le statut et signale les problèmes.
3. `График_примерок.Номер_мастера`, `Результат` : « просмотр результатов примерок ».
   Le CHECK `Дата >= GETDATE()` de cette table est retiré, sinon on ne pourrait pas noter le résultat d'un essayage passé
   (la règle reste vérifiée par l'application à la création).
4. `Мастер.Работает` : licencier un maître sans effacer son historique.
5. `Клиент.user_id`, `Мастер.user_id` : lien avec le compte de connexion.
6. `Запись.Тип_записи` passe de VARCHAR à NVARCHAR (texte russe garanti).

Les colonnes existantes, leurs types et vos autres contraintes ne sont pas modifiés.

## 7. Structure

```
config/settings.py           paramètres (connexion SQL Server, PROVERKA_V_BAZE)
atelier/models.py            les 12 tables + contraintes + logique métier
atelier/views.py             pages par rôle
atelier/forms.py             formulaires
atelier/roles.py             rôles (groupes Django) et contrôle d'accès
atelier/admin.py             interface d'administration
atelier/templates/atelier/   pages HTML
atelier/static/atelier/css/  feuille de style (charte graphique complète)
atelier/static/atelier/js/   scripts de l'interface
atelier/static/atelier/fonts/ polices locales (cyrillique)
atelier/management/commands/zapolnit.py   comptes et données de test
atelier/management/commands/proverit_bd.py vérification des tables
atelier/migrations/0002_dopolnit_tablicy.py colonnes ajoutées (SQL Server)
atelier/tests.py             tests automatiques
sql/ogranicheniya_p3_3.sql   les 26 contraintes du § 3.3 (SQL Server)
docs/ogranicheniya.md        chaque contrainte avec son code
```

## Problèmes fréquents

- `Can't open lib 'ODBC Driver 17 for SQL Server'` → installez le pilote ODBC ou définissez `DB_DRIVER` sur la version installée.
- `Login failed` / serveur introuvable → vérifiez `DB_HOST` (exactement le nom affiché dans SSMS à la connexion).
- `proverit_bd` affiche ОШИБКА → une colonne porte un autre nom dans votre base : envoyez la sortie de la commande.
