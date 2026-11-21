# bench-29

## clamp
check: python3 -c "from f01 import clamp; assert clamp(9, 0, 5) == 5 and clamp(-1, 0, 5) == 0"

## fizz
check: python3 -c "from f02 import fizz; assert fizz(9) == 'Fizz' and fizz(4) == '4'"

## slug
check: python3 -c "from f03 import slug; assert slug('Hello Big World') == 'hello-big-world'"

## mul
check: python3 -c "from f04 import mul; assert mul(4, 3) == 12"

## vowels
check: python3 -c "from f05 import vowels; assert vowels('Banana') == 3"
