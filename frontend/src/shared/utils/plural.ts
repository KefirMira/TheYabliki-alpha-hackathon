/**
 * Число со словом в нужной форме: plural(2, ['инсайт', 'инсайта',
 * 'инсайтов']) → «2 инсайта».
 */
export const plural = (
  count: number,
  [one, few, many]: [string, string, string]
): string => {
  const mod10 = count % 10
  const mod100 = count % 100
  const word =
    mod10 === 1 && mod100 !== 11
      ? one
      : mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)
        ? few
        : many
  return `${count} ${word}`
}
