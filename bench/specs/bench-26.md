# bench-26

## mean
check: python3 -c "from f01 import mean; assert mean([1, 2, 3, 6]) == 3"

## clamp
check: python3 -c "from f02 import clamp; assert clamp(9, 0, 5) == 5 and clamp(-1, 0, 5) == 0"

## vowels
check: python3 -c "from f03 import vowels; assert vowels('Banana') == 3"
