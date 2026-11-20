# bench-10

## fizz
check: python3 -c "from f01 import fizz; assert fizz(9) == 'Fizz' and fizz(4) == '4'"

## is_even
check: python3 -c "from f02 import is_even; assert is_even(4) and not is_even(3)"

## slug
check: python3 -c "from f03 import slug; assert slug('Hello Big World') == 'hello-big-world'"

## sub
check: python3 -c "from f04 import sub; assert sub(5, 3) == 2"

## vowels
check: python3 -c "from f05 import vowels; assert vowels('Banana') == 3"
