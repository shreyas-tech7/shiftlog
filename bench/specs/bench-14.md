# bench-14

## add
check: python3 -c "from f01 import add; assert add(2, 3) == 5"

## is_even
check: python3 -c "from f02 import is_even; assert is_even(4) and not is_even(3)"

## clamp
check: python3 -c "from f03 import clamp; assert clamp(9, 0, 5) == 5 and clamp(-1, 0, 5) == 0"

## palin
check: python3 -c "from f04 import palin; assert palin('abba') and not palin('abc')"

## vowels
check: python3 -c "from f05 import vowels; assert vowels('Banana') == 3"
