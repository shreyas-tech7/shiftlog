# bench-06

## add
check: python3 -c "from f01 import add; assert add(2, 3) == 5"

## is_even
check: python3 -c "from f02 import is_even; assert is_even(4) and not is_even(3)"

## mean
check: python3 -c "from f03 import mean; assert mean([1, 2, 3, 6]) == 3"

## palin
check: python3 -c "from f04 import palin; assert palin('abba') and not palin('abc')"
