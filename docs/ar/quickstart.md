---
title: البدء السريع
description: جرّب safha على العيّنة المرفقة ثم على كتابك في دقيقة.
order: 3
---

# البدء السريع

## العيّنة المرفقة

```bash
uvx safha demo
```

يعالج هذا الأمر عيّنتين من كتب الملك العام مرفقتين بالأداة: ست صفحات من ترجمة «الآثار الباقية» للبيروني (لندن 1879)،
وخمس لقطات ميكروفيلم لمخطوط عربي في كل لقطة صفحتان. ويكتب في مجلد `safha-demo` ملف PDF مقصوصًا لكل عيّنة، ووصفة
JSON، وصورة «قبل | بعد» تُظهر الإطار بالأحمر على الصورة الأصلية ثم ما يراه القارئ.

## كتابك

```bash
safha crop book.pdf
```

يكتب الملف `book.safha.pdf` بجانب الأصل، ويطبع ملخّصًا مثل:

```text
book.pdf: 412 pages (398 text), mode CROP
  why: text 22 % larger; 9 tilted pages
  one page size 341.0 x 520.9 pt, text 22 % larger on screen
     9 turned level: p. 14, 15, 88, ...
     2 lines at two angles, left as scanned: p. 203, 391
  412 pages: 410 cropped, 9 turned/moved, 3 scaled; 48.20 MB -> 48.21 MB (+6.1 KB); images untouched; reversible
```

ولا يظهر الملف الناتج باسمه إلا بعد أن يجتاز الفحص كله؛ فإن رُفضت النتيجة لم يبقَ على القرص شيء.

!!! tip "نصيحة"
    إذا قالت الأداة «nothing to do» فقد ذكرت السبب في السطر نفسه. فإن كان `a good scan` فالكتاب مصوّر تصويرًا جيدًا
    والقصّ لا يزيده إلا قليلًا، ولقصّه مع ذلك: `safha crop book.pdf --profile reader`. وإن كان `few text pages`
    فالكتاب أقصر من خمس صفحات نص، ولقصّه مع ذلك استعمل الخيار الذي تقترحه الرسالة، مثل
    `safha crop book.pdf --set min_text_pages=3`.

## الكتب العربية ذات الصفحات المزدوجة

إذا كانت كل لقطة تحمل صفحتين فاطلب ترتيب العربية (اليمنى أولًا):

```bash
safha crop book.pdf --rtl
```

## ما التالي؟

- [قصّ كتاب كامل](guides/crop-a-book.md) بخياراته كلها.
- [مراجعة النتيجة](guides/review.md) قبل نقلها إلى الهاتف.
