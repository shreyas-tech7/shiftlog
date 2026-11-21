# bench-25

## add
check: python3 -c "from f01 import add; assert add(2, 3) == 5"

## palin
check: python3 -c "from f02 import palin; assert palin('abba') and not palin('abc')"

## is_even
check: python3 -c "from f03 import is_even; assert is_even(4) and not is_even(3)"
