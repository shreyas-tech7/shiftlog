# bench-23

## palin
check: python3 -c "from f01 import palin; assert palin('abba') and not palin('abc')"

## mean
check: python3 -c "from f02 import mean; assert mean([1, 2, 3, 6]) == 3"

## dedupe
check: python3 -c "from f03 import dedupe; assert dedupe([3, 1, 3, 2]) == [3, 1, 2]"

## mul
check: python3 -c "from f04 import mul; assert mul(4, 3) == 12"
