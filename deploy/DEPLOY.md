# Deploiement Fleet Hub V2 sur VPS Infomaniak

## 1. DNS (Panel Infomaniak)
```
A      hub   → [IPv4 du VPS]
AAAA   hub   → [IPv6 du VPS]
```

## 2. Cloner et installer
```bash
cd /home/fleet
git clone <repo-url> fleet-webhooks-v2
cd fleet-webhooks-v2
git checkout claude/serene-antonelli
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Editer les variables d'env dans le service
```bash
sudo nano /etc/systemd/system/fleet-hub-v2.service
# Modifier : DATABASE_URL, FLEET_WEBHOOK_TOKEN, SHIPDAY_TOKEN, User, WorkingDirectory
```

## 4. Installer le service systemd
```bash
sudo cp deploy/fleet-hub-v2.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable fleet-hub-v2
sudo systemctl start fleet-hub-v2
sudo systemctl status fleet-hub-v2
```

## 5. Configurer Nginx
```bash
sudo cp deploy/nginx-hub.conf /etc/nginx/sites-available/hub.swisslivraisonpro.ch
sudo ln -s /etc/nginx/sites-available/hub.swisslivraisonpro.ch /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## 6. SSL
```bash
sudo certbot --nginx -d hub.swisslivraisonpro.ch
```

## 7. Verifier
```bash
curl https://hub.swisslivraisonpro.ch/health
# → {"status":"ok","service":"fleet-hub","database":"connected"}
```

## Commandes utiles
```bash
sudo systemctl restart fleet-hub-v2    # redemarrer
sudo systemctl stop fleet-hub-v2       # arreter
sudo journalctl -u fleet-hub-v2 -f     # voir les logs en temps reel
```
