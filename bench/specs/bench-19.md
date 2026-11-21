# bench-19

## reverse
check: python3 -c "from f01 import reverse; assert reverse('abc') == 'cba'"

## is_even
check: python3 -c "from f02 import is_even; assert is_even(4) and not is_even(3)"

## sub
check: python3 -c "from f03 import sub; assert sub(5, 3) == 2"
