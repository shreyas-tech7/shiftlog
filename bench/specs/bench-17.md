# bench-17

## dedupe
check: python3 -c "from f01 import dedupe; assert dedupe([3, 1, 3, 2]) == [3, 1, 2]"

## vowels
check: python3 -c "from f02 import vowels; assert vowels('Banana') == 3"

## is_even
check: python3 -c "from f03 import is_even; assert is_even(4) and not is_even(3)"

## sub
check: python3 -c "from f04 import sub; assert sub(5, 3) == 2"
