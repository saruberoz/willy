# Website shows 502 Bad Gateway, 504 Gateway Timeout, or PHP stopped working
Keywords: 502 bad gateway 504 gateway timeout 503 service unavailable php php-fpm fastcgi upstream nginx apache proxy_pass reverse proxy socket connect() failed no live upstreams cgi-fcgi status page backend down website down

## What it means
The web server (nginx or Apache) works, but the program behind it (PHP-FPM, a Node/Python app, another server) didn't answer (502) or answered too slowly (504).

## Check (read-only)
1. The web server's error log says which backend failed and how: `sudo tail -n 30 /var/log/nginx/error.log` (Apache: `/var/log/apache2/error.log` or `/var/log/httpd/error_log`). Look for "connect() failed", "No such file or directory" (wrong socket path), "Permission denied" (socket permissions) or "upstream timed out" (504).
2. Is the backend running? `systemctl list-units --no-pager | grep -iE 'php|fpm|gunicorn|uwsgi|node'`, then `systemctl status <backend> --no-pager`
3. Where does the web server send requests, and does that exist? `grep -rE 'fastcgi_pass|proxy_pass' /etc/nginx/ | grep -v '#'`; for a socket: `ls -l /run/php/`. The version in the socket name (for example php8.3-fpm.sock) must match what's installed.
4. Backend's own log: `journalctl -u <php-fpm service> -n 50 --no-pager`
5. Ask PHP-FPM directly (optional, needs the status page enabled with `pm.status_path = /status` and the `libfcgi-bin` package):
   `SCRIPT_NAME=/status SCRIPT_FILENAME=/status REQUEST_METHOD=GET cgi-fcgi -bind -connect /run/php/<php>-fpm.sock`
   It shows active, idle and maximum children; "max children reached" means it's overloaded.

## Fixes
- Backend stopped or crashed: `sudo systemctl restart <php-fpm service>`, then read its log to see why it stopped.
- Socket path changed after a PHP upgrade: update `fastcgi_pass` to the new socket, test with `sudo nginx -t`, then `sudo systemctl reload nginx`.
- Permission denied on the socket: `listen.owner` and `listen.group` in the FPM pool config (`/etc/php/<version>/fpm/pool.d/www.conf`) must match the web server user (usually `www-data`).
- Overloaded (504, max children reached): raise `pm.max_children` in the pool config if there's RAM to spare, or find the slow requests.
- See also the "service won't start" and "can't reach a server or port" guides.

## Undo notes
Config edits are restored with /undo; restart or reload the service afterwards.
