# bench-01

## is_even
check: python3 -c "from f01 import is_even; assert is_even(4) and not is_even(3)"

## sub
check: python3 -c "from f02 import sub; assert sub(5, 3) == 2"

## slug
check: python3 -c "from f03 import slug; assert slug('Hello Big World') == 'hello-big-world'"
