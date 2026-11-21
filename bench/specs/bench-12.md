# bench-12

## mul
check: python3 -c "from f01 import mul; assert mul(4, 3) == 12"

## palin
check: python3 -c "from f02 import palin; assert palin('abba') and not palin('abc')"

## vowels
check: python3 -c "from f03 import vowels; assert vowels('Banana') == 3"

## is_even
check: python3 -c "from f04 import is_even; assert is_even(4) and not is_even(3)"
