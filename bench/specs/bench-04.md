# bench-04

## sub
check: python3 -c "from f01 import sub; assert sub(5, 3) == 2"

## fizz
check: python3 -c "from f02 import fizz; assert fizz(9) == 'Fizz' and fizz(4) == '4'"

## slug
check: python3 -c "from f03 import slug; assert slug('Hello Big World') == 'hello-big-world'"

## dedupe
check: python3 -c "from f04 import dedupe; assert dedupe([3, 1, 3, 2]) == [3, 1, 2]"
