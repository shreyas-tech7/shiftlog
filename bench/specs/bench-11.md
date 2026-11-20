# bench-11

## clamp
check: python3 -c "from f01 import clamp; assert clamp(9, 0, 5) == 5 and clamp(-1, 0, 5) == 0"

## add
check: python3 -c "from f02 import add; assert add(2, 3) == 5"

## vowels
check: python3 -c "from f03 import vowels; assert vowels('Banana') == 3"

## mul
check: python3 -c "from f04 import mul; assert mul(4, 3) == 12"
