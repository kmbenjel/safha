---
title: التثبيت
description: تثبيت صفحة بأمر واحد على لينكس وماك وويندوز.
order: 2
---

# التثبيت

تحتاج صفحة إلى بايثون 3.10 أو أحدث، ولا تعتمد إلا على أربع مكتبات معروفة: PyMuPDF وNumPy وSciPy وPillow.

## الطريقة الأسهل: uv

إن كان عندك [uv](https://docs.astral.sh/uv/) فلا حاجة إلى تثبيت شيء؛ شغّل الأداة مباشرة:

```bash
uvx safha demo
```

## pipx

```bash
pipx install safha
safha --version
```

## pip داخل بيئة افتراضية

```bash
python -m venv .venv
source .venv/bin/activate
pip install safha
```

وعلى ويندوز تُفعَّل البيئة بالأمر `.venv\Scripts\activate`.

## من المصدر

```bash
git clone https://github.com/kmbenjel/safha
cd safha
make install
```

!!! note "ملاحظة"
    لا تحتاج صفحة إلى Ghostscript ولا إلى برامج خارجية: القراءة والكتابة كلتاهما بمكتبة PyMuPDF.
