
To start the program specify the following arguments:

* `--symbol` (default: `"ETHUSDT"`)
* `--volume` (default: `100.`), 
* `--amountDif` (default: `1.`),
* `--number` (default: `2`),
* `--side` (default: `SELL`),
* `--priceMin` (default: `1908+5`),
* `--priceMax` (default: `1908-5`).


You can also see the usage below:

```
python3 orders.py --help
usage: orders.py [-h] [--symbol SYMBOL] [--volume VOLUME] [--amountDif AMOUNTDIF] [--number NUMBER] [--side SIDE] [--priceMin PRICEMIN] [--priceMax PRICEMAX]

options:
  -h, --help            show this help message and exit
  --symbol SYMBOL       Market pair
  --volume VOLUME       Volume in USDT
  --amountDif AMOUNTDIF
                        USDT range within which the volume is randomly selected in both upward and downward directions.
  --number NUMBER       Number of orders
  --side SIDE           SELL or BUY
  --priceMin PRICEMIN   Min price range.
  --priceMax PRICEMAX   Max price range.
```
