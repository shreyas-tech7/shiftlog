# bench-03

## slug
check: python3 -c "from f01 import slug; assert slug('Hello Big World') == 'hello-big-world'"

## reverse
check: python3 -c "from f02 import reverse; assert reverse('abc') == 'cba'"

## is_even
check: python3 -c "from f03 import is_even; assert is_even(4) and not is_even(3)"

## mean
check: python3 -c "from f04 import mean; assert mean([1, 2, 3, 6]) == 3"
