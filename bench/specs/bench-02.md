# bench-02

## fizz
check: python3 -c "from f01 import fizz; assert fizz(9) == 'Fizz' and fizz(4) == '4'"

## vowels
check: python3 -c "from f02 import vowels; assert vowels('Banana') == 3"

## is_even
check: python3 -c "from f03 import is_even; assert is_even(4) and not is_even(3)"

## mul
check: python3 -c "from f04 import mul; assert mul(4, 3) == 12"

## slug
check: python3 -c "from f05 import slug; assert slug('Hello Big World') == 'hello-big-world'"
