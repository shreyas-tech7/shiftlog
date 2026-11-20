# bench-09

## add
check: python3 -c "from f01 import add; assert add(2, 3) == 5"

## mean
check: python3 -c "from f02 import mean; assert mean([1, 2, 3, 6]) == 3"

## sub
check: python3 -c "from f03 import sub; assert sub(5, 3) == 2"
