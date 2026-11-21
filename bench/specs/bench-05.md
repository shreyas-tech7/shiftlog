# bench-05

## vowels
check: python3 -c "from f01 import vowels; assert vowels('Banana') == 3"

## slug
check: python3 -c "from f02 import slug; assert slug('Hello Big World') == 'hello-big-world'"

## palin
check: python3 -c "from f03 import palin; assert palin('abba') and not palin('abc')"

## clamp
check: python3 -c "from f04 import clamp; assert clamp(9, 0, 5) == 5 and clamp(-1, 0, 5) == 0"
