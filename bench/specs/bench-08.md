# bench-08

## mean
check: python3 -c "from f01 import mean; assert mean([1, 2, 3, 6]) == 3"

## reverse
check: python3 -c "from f02 import reverse; assert reverse('abc') == 'cba'"

## sub
check: python3 -c "from f03 import sub; assert sub(5, 3) == 2"

## fizz
check: python3 -c "from f04 import fizz; assert fizz(9) == 'Fizz' and fizz(4) == '4'"

## add
check: python3 -c "from f05 import add; assert add(2, 3) == 5"
