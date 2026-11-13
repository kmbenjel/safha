# Sources of the sample pages

Every page in `tests/fixtures/`, `src/safha/data/` and `docs/media/` comes from a public-domain scan on the Internet
Archive. The fixtures are small excerpts rebuilt by `scripts/make_fixtures.py` (JPEG pages re-saved smaller, the Latin
pages made bitonal and encoded as lossless JBIG2, the Urdu pages copied object for object with their original CCITT G4
streams). The synthetic pages in `tests/synth.py` are drawn by the tests themselves.

| File | Pages used | Source | Year | Licence |
|---|---|---|---|---|
| `tests/fixtures/arabic-leiden.pdf` | scan pages 30-35 | al-Tabari, *Tarikh al-rusul wa-al-muluk*, ed. M. J. de Goeje et al., Leiden: Brill, 1879. University of Toronto copy. <https://archive.org/details/tarkhalrusulwaal01abaruoft> | 1879 | Public domain |
| `tests/fixtures/arabic-bulaq.pdf` | scan pages 100-105 | al-Maqrizi, *Kitab al-Mawa'iz wa-al-i'tibar* (al-Khitat), Bulaq, 1853. University of Toronto copy. <https://archive.org/details/kitbalmawiwaalit01maqruoft> | 1853 | Public domain |
| `tests/fixtures/latin-jbig2.pdf`, `src/safha/data/sample-latin.pdf` | scan pages 31, 32, 101, 102, 201, 202 | al-Biruni, *The Chronology of Ancient Nations*, tr. C. E. Sachau, London, 1879. University of Toronto copy. <https://archive.org/details/chronologyofanci00biru> | 1879 | Public domain |
| `tests/fixtures/spreads.pdf`, `src/safha/data/sample-spreads.pdf`, `docs/media/hero.webp`, `docs/media/card.webp` | microfilm frames 20, 30, 40, 50, 60 | *Arabic manuscripts on medicine and science* [microform], reel 28, UCLA Library (Louise M. Darling Biomedical Library). <https://archive.org/details/arabicmanuscript28loui> | manuscript before 1900 | Public domain (pre-1900 manuscript; faithful reproduction) |
| `tests/fixtures/urdu-ccitt.pdf` | PDF pages 19-22, 31-32 | *Tamreen as-Sarf*, 1857. Digital Library of India. <https://archive.org/details/in.ernet.dli.2015.361017> | 1857 | Public domain |
| `docs/media/deskew.gif` | a page of the 40-page bench excerpt | Ibn Khaldun, *al-Muqaddimah*, Cairo: Matba'at al-Taqaddum, 1904. University of Toronto copy. <https://archive.org/details/almuqaddimah00ibnk> | 1904 | Public domain |
| `docs/media/compare.webp` | a page of the 40-page bench excerpt | al-Biruni, *The Chronology of Ancient Nations*, London, 1879 (as above) | 1879 | Public domain |

The benchmark corpus (`bench/fetch_corpus.py`) lists every book it downloads, with its year and licence, in
`corpus.tsv`; all are works published before 1931 or manuscripts, public domain in the United States.
