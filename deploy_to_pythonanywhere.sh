git pull
cd frontend/
npm install
npm run generate
cd ../backend
source python-env/bin/activate
pip3 install -r requirements.txt
python3 qurry_api/manage.py makemigrations users questions media
python3 qurry_api/manage.py migrate users
python3 qurry_api/manage.py makemigrations
python3 qurry_api/manage.py migrate
touch /var/www/www_qurry_de_wsgi.py

