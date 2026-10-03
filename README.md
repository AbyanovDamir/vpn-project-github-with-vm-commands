# VPN OAuth Lab: WireGuard + многостраничное веб-приложение + OAuth 2.0

Готовый учебный проект для двух Ubuntu-машин:

- `wg-server-damir`, пользователь `damir1` — WireGuard-сервер, веб-приложение, OAuth-сервер и firewall;
- `wg-client-damir`, пользователь `damir2` — WireGuard-клиент и браузер.

Веб-приложение имеет главную страницу `/`, страницу `/about` и защищённую страницу `/private`. Авторизация реализована по OAuth 2.0 Authorization Code с PKCE. Порты веб-приложения `8080/tcp` и OAuth-сервера `9000/tcp` разрешены firewall только через интерфейс `wg0`. Без VPN приложение недоступно.

> Команды установки рассчитаны на Ubuntu 24.04 LTS и выполняются из корня клонированного репозитория.

## 1. Состав репозитория

```text
app/                         исходный код веб-приложения и OAuth-сервера
deploy/systemd/              systemd units
deploy/wireguard/            шаблоны WireGuard без секретных ключей
deploy/nftables.conf         firewall: веб-порты принимаются только с wg0
scripts/install_server.sh    установка серверной части
scripts/install_client.sh    установка клиентской части
scripts/add_client.sh        добавление клиента на сервер
scripts/status.sh            диагностика сервера или клиента
scripts/restart.sh           перезапуск компонентов
scripts/test_client.sh       проверка запрета без VPN и работы с VPN
scripts/cleanup.sh           удаление конфигурации лабораторной работы
scripts/verify_project.py    статическая проверка состава и настроек
scripts/integration_oauth_test.py  интеграционный тест OAuth 2.0 + PKCE
evidence/                    скриншоты выполненной работы
report/vpn_oauth_report.pdf  готовый отчёт
```

Приватные ключи WireGuard, `/etc/vpn-lab.env` и реальные пароли в репозиторий не входят и создаются непосредственно на виртуальных машинах.

## 2. Загрузка проекта на GitHub

На Windows откройте PowerShell в папке проекта:

```powershell
Set-Location D:\project\vpn-oauth-project
git init -b main
git add .
git commit -m "Initial WireGuard OAuth lab"
git remote add origin https://github.com/<OWNER>/<REPOSITORY>.git
git push -u origin main
```

Если `git init -b main` не поддерживается установленной версией Git, выполните `git init`, затем `git branch -M main`. Перед `push` создайте пустой репозиторий на GitHub и замените `<OWNER>/<REPOSITORY>` на его адрес. Не добавляйте README или лицензию через веб-интерфейс GitHub: они уже есть в проекте.

## 3. Клонирование на обеих виртуальных машинах

Выполнить отдельно на `wg-server-damir` под `damir1` и на `wg-client-damir` под `damir2`:

```bash
sudo apt update
sudo apt install -y git
git clone https://github.com/<OWNER>/<REPOSITORY>.git
cd <REPOSITORY>
hostname
whoami
pwd
```

Ожидается `wg-server-damir` / `damir1` на сервере и `wg-client-damir` / `damir2` на клиенте.

## 4. Сетевая схема

| Назначение | Адрес |
|---|---|
| LAN сервера | `192.168.100.10` |
| LAN клиента | `192.168.100.20` |
| WireGuard сервера | `10.20.0.1/24` |
| WireGuard клиента | `10.20.0.2/24` |
| WireGuard | `192.168.100.10:51820/udp` |
| Веб-приложение через VPN | `http://10.20.0.1:8080` |
| OAuth-сервер через VPN | `http://10.20.0.1:9000` |

Для VirtualBox обе машины должны находиться в одной Host-only Network или Internal Network. Приведённые LAN-адреса можно изменить переменными окружения в командах установки.

## 5. Установка сервера

На `wg-server-damir`:

```bash
cd <REPOSITORY>
sudo DEMO_USER='student' DEMO_PASSWORD='Замените-на-сложный-пароль' \
  bash scripts/install_server.sh
sudo cat /etc/vpn-lab-keys/server.pub
```

Скопируйте напечатанный публичный ключ сервера. Скрипт установит WireGuard, nftables, Python и curl, создаст пользователя `vpnlab`, развернёт приложение в `/opt/vpn-lab`, сгенерирует серверные ключи и случайный секрет сессии, а затем запустит `wg-quick@wg0`, `nftables`, `oauth-server` и `vpn-web`. Исходный `/etc/nftables.conf` сохраняется в `/etc/nftables.conf.vpn-lab.bak`, если резервной копии ещё нет.

Проверка сервера:

```bash
bash scripts/status.sh server
sudo systemctl is-active wg-quick@wg0 nftables oauth-server vpn-web
sudo wg show
sudo nft list ruleset
```

## 6. Установка клиента

На `wg-client-damir` подставьте публичный ключ сервера:

```bash
cd <REPOSITORY>
sudo SERVER_PUBLIC_KEY='<PUBLIC_KEY_СЕРВЕРА>' \
  SERVER_ENDPOINT='192.168.100.10:51820' \
  bash scripts/install_client.sh
sudo cat /etc/vpn-lab-keys/client.pub
```

Скопируйте напечатанный публичный ключ клиента. При другой адресации:

```bash
sudo SERVER_PUBLIC_KEY='<PUBLIC_KEY_СЕРВЕРА>' \
  SERVER_ENDPOINT='<LAN_IP_СЕРВЕРА>:51820' \
  CLIENT_ADDRESS='10.20.0.2/24' \
  VPN_NETWORK='10.20.0.0/24' \
  bash scripts/install_client.sh
```

## 7. Добавление клиента на сервер

Вернитесь на `wg-server-damir` и подставьте публичный ключ клиента:

```bash
cd <REPOSITORY>
sudo CLIENT_PUBLIC_KEY='<PUBLIC_KEY_КЛИЕНТА>' bash scripts/add_client.sh
sudo wg show
```

После этого на клиенте:

```bash
sudo systemctl restart wg-quick@wg0
bash scripts/status.sh client
```

В выводе `sudo wg show` должен появиться `latest handshake`, а `ping -c 3 10.20.0.1` должен завершиться успешно.

## 8. Ручная проверка приложения и OAuth 2.0

На `wg-client-damir` при включённом VPN откройте `http://10.20.0.1:8080`. Проверьте `/` и `/about`, нажмите «Войти через OAuth 2.0», введите заданные при установке `DEMO_USER` и `DEMO_PASSWORD`. После успешного входа откроется `/private`.

Проверка из терминала:

```bash
curl -i http://10.20.0.1:8080/health
curl -i http://10.20.0.1:8080/
curl -i http://10.20.0.1:8080/about
```

## 9. Полное автоматическое тестирование с клиента

Скрипт временно выключает VPN, убеждается, что приложение недоступно, включает VPN обратно, проверяет страницы и выполняет полный OAuth 2.0 Authorization Code + PKCE flow:

```bash
cd <REPOSITORY>
DEMO_USER='student' DEMO_PASSWORD='Заданный-на-сервере-пароль' \
  SERVER_LAN_URL='http://192.168.100.10:8080' \
  bash scripts/test_client.sh
```

Успешный итог: `Все клиентские проверки пройдены.` Скрипт восстанавливает первоначально включённый VPN даже при ошибке.

Отдельная ручная проверка «только через VPN»:

```bash
sudo systemctl stop wg-quick@wg0
curl --connect-timeout 3 http://10.20.0.1:8080/health
curl --connect-timeout 3 http://192.168.100.10:8080/health
sudo systemctl start wg-quick@wg0
curl http://10.20.0.1:8080/health
```

Первые две команды `curl` должны завершиться ошибкой, последняя — вернуть `{"status":"ok"}`.

## 10. Локальная проверка без VM

Она проверяет приложение и OAuth, но не WireGuard/firewall. Нужен Python 3.9 или новее.

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python scripts/verify_project.py
python app/oauth_server.py &
OAUTH_PID=$!
python app/web_app.py &
WEB_PID=$!
python scripts/integration_oauth_test.py
kill "$WEB_PID" "$OAUTH_PID"
```

Windows PowerShell — команды запуска серверов выполняются в двух отдельных окнах, тест — в третьем:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python scripts\verify_project.py
python app\oauth_server.py
python app\web_app.py
python scripts\integration_oauth_test.py
```

GitHub Actions автоматически запускает статическую проверку, проверку синтаксиса shell-скриптов и интеграционный OAuth-тест при каждом `push` и `pull_request`.

## 11. Перезапуск

```bash
# сервер
sudo bash scripts/restart.sh server

# клиент
sudo bash scripts/restart.sh client
```

Отдельный компонент можно перезапустить командой `sudo systemctl restart vpn-web`, `sudo systemctl restart oauth-server` или `sudo systemctl restart wg-quick@wg0`.

## 12. Обновление после git pull

Повторный запуск серверного установщика обновляет код и unit-файлы, но не перезаписывает ключи и `/etc/vpn-lab.env`:

```bash
# сервер
cd <REPOSITORY>
git pull --ff-only
sudo bash scripts/install_server.sh
sudo bash scripts/restart.sh server

# клиент: для обычного обновления тестов
cd <REPOSITORY>
git pull --ff-only
bash scripts/status.sh client
```

Повторный `install_client.sh` перезаписывает `wg0.conf`, но сохраняет существующую пару ключей.

## 13. Полная очистка

Команды удаляют конфигурацию лабораторной работы, ключи и сервисы. Системные пакеты остаются. На сервере по возможности восстанавливается резервная копия nftables.

```bash
# сервер
sudo bash scripts/cleanup.sh server --yes

# клиент
sudo bash scripts/cleanup.sh client --yes
```

Удаление клонированной папки выполняйте только после проверки `pwd`:

```bash
cd ..
pwd
rm -rf -- <REPOSITORY>
```

## 14. Диагностика

```bash
hostname
whoami
ip -brief address
sudo wg show
sudo systemctl --no-pager --full status wg-quick@wg0 nftables oauth-server vpn-web
sudo journalctl -u wg-quick@wg0 -u nftables -u oauth-server -u vpn-web -n 100 --no-pager
sudo ss -lntup
sudo nft list ruleset
curl -v --connect-timeout 3 http://10.20.0.1:8080/health
```

Типичные причины ошибок:

- нет handshake: неверный публичный ключ, endpoint или UDP/51820 блокируется сетью VM;
- `connection refused`: сервис не запущен или приложение не слушает `10.20.0.1`;
- timeout по LAN при работающем VPN — ожидаемое поведение, веб-порты закрыты на LAN-интерфейсе;
- OAuth callback error: проверьте `APP_BASE_URL`, `OAUTH_URL` и `OAUTH_REDIRECT_URI` в `/etc/vpn-lab.env`;
- после изменения пароля в `/etc/vpn-lab.env` выполните `sudo systemctl restart oauth-server`.

## 15. Безопасность

Это учебный стенд. Для реальной эксплуатации нужны HTTPS, полноценный OAuth/OIDC-провайдер, защищённое хранилище секретов, ротация ключей, ограничение SSH и централизованный аудит. Никогда не публикуйте содержимое `/etc/wireguard`, `/etc/vpn-lab-keys` и `/etc/vpn-lab.env`.

