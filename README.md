# tiktok-hoarder
Програма для завантаження відео в ТікТоці і їх послідовної відправки у Телеграм-канал чи особисті повідомлення.

## Особливості
- Можна запускати як на Лямбді, так і на своєму комп'ютері, але в другому випадку доведеться зробити деякі зміни.
- Тягне 8 відео кожен раз що скрипт запущено.
- Підтримує мультипотоковість.
- Не потребує ALB чи будь-чого іншого перед лямбдою чи машиною, яка запускає скрипт. Достатньо однієї лінії в cron.
- Не підтримує Windows.
- Підтримує геолок.
- Всі логи (за умови використання шаблону CloudFormation) видаляються через день.

## Вимоги до старта
- boto3 і requests
- Печивки з ТікТока, при цьому мають бути у форматі, який генерує Файрфокс (принаймні `http.cookiejar` викликає `MozillaCookieJar()`). Має сенс встановити cookies.txt з базару додатків браузера.
- Бот у Телеграмі.
- Наявність [yt-dlp](https://github.com/yt-dlp/yt-dlp) також обов'язкова.

Ось такий розміщений у тій самій теці що й lambda_function.py `yt-dlp.conf`. Фейсбучний юзер-агент потрібен для того, щоб ТікТок надто сильно не гавкав:
```
--user-agent facebookexternalhit/1.1
--force-ipv4
--no-geo-bypass
-o /tmp/%(uploader)s-%(id)s.mp4
```

### Розробка без лямбди
Скрипт розраховує, що у середовищних змінних (environment variables) проставлені наступні значення:
- chat_id => куди відправляти всі відео
- bucket => "local_storage:<абсолютний чи відносний шлях до файла з кукіз>"; у лямбді це ім'я S3 відра
- token => токен бота у Телеграмі без "bot"
- feedback => chat_id діалога чи канала, куди мають йти повідомлення, якщо не вдалося завантажити відео; якщо не хочеш нікуди відправляти, став значення "/dev/null"
- geolock => регіон двозначним кодом ISO-3166 з якого мають надходити усі відео у фіді акаунта

У кінці `lambda_function.py` доведеться додати наступний код:
```python
lambda_handler("te", "te")
```

### Розробка з лямбдою
Код лямбди доведеться оновлювати руками, шаблон CloudFormation створить лямбду із мінімально заповненим файлом `main.py` тільки щоб уникнути помилки.

Архів слід формувати наступним чином:
```bash
$ tree tiktok-hoarder
 |-lambda_function.py
 |-package
 | |-<your libraries installed via `pip install -r requirements --target ./tiktok-hoarder/package`>
 |-yt-dlp
 |-yt-dlp.conf

$ rm -f package.zip && cd package && zip -qr ../package.zip . && cd ../ && zip package.zip lambda_function.py yt-dlp yt-dlp.conf
```

## Пост-скриптум для загального розвитку
### Де ТікТок береже відео без вотермарок
Ось цей ендпоїнт (залежно від регіону він інший) відповідальний за аутентифікацію користувача. Вимагає email та password у, судячи з нутрощів вкладки Network у браузері, невідомому мені хешованому форматі, але окрім цього генерує(?) ще [sid_tt](https://github.com/lucasintel/tiktok-passport). Публічної документації не існує, а реверс за допомогою [HTTP toolkit](https://httptoolkit.com/) чи будь-якого іншого Вайршарка не дає нічого значущого, бо весь трафік зашифрований, а сервера не приймають самопальні сертифікати. Остання опція - Frida (японці у своїй частині Інтернета мають гайди на тему реверса ТікТока) чи подібна програма, але в мене руки не дійшли.
```
https://api16-normal-c-useast1a.tiktokv.com
```

Його ж використовує yt-dlp для завантаження відео без вотермарок; варто додати, що будь-який `apiXY-normal-c` сервер містить у собі відео без них.

### Конфіг ТікТока
Додаткові цікавинки можна подивитися [тут](https://www.diffchecker.com/nwuQhTQq/) (копії оригінала і нового файлів додані до теки readme, а сторінку [заархівовано](https://archive.is/LcG9m)), вочевидь один з розробників випадково закинув у публічний доступ дві версії конфіга ТікТока.

### Стягування усіх відео конкретного користувача
Наступний шмат кода стягне список усіх відео конкретного користувача. Не потребує аутентифікації за умови, що користувач не запривачений.
```python
res = requests.get("https://www.tiktok.com/@qnesko007", headers={"Content-Type": "application/json"})
output = res.content.decode()
output = output.replace('<script id="SIGI_STATE"', '\n<script id="SIGI_STATE"'); output = output.replace('</script>', '\n</script>')
for line in output.split("\n"):
    if "SIGI_STATE" in line:
        target = line
        break
target = target.replace('<script id="SIGI_STATE" type="application/json">', ""); target = target.replace('</script>', "")
for item in json.loads(target):
    print (item)
target = json.loads(target)
print (target["ItemList"]["user-post"]["list"])
```
