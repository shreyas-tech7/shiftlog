# bench-24

## mean
check: python3 -c "from f01 import mean; assert mean([1, 2, 3, 6]) == 3"

## vowels
check: python3 -c "from f02 import vowels; assert vowels('Banana') == 3"

## reverse
check: python3 -c "from f03 import reverse; assert reverse('abc') == 'cba'"
