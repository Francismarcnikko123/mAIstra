import { SourceRange } from '../../services/similarity.service';

export interface SourceFragment {
  text: string;
  matched: boolean;
}
export interface SourceLine {
  number: number;
  fragments: SourceFragment[];
}

// Tree-sitter columns count UTF-8 bytes; rendering counts JavaScript characters.
export function highlightSource(
  code: string,
  ranges: SourceRange[],
): SourceLine[] {
  const encoder = new TextEncoder();
  return code.split('\n').map((line, row) => {
    let byte = 0;
    const fragments: SourceFragment[] = [];
    for (const character of line) {
      const end = byte + encoder.encode(character).length;
      const matched = ranges.some(
        (range) =>
          row >= range.start.row &&
          row <= range.end.row &&
          (row > range.start.row || end > range.start.column) &&
          (row < range.end.row || byte < range.end.column),
      );
      const previous = fragments.at(-1);
      if (previous?.matched === matched) previous.text += character;
      else fragments.push({ text: character, matched });
      byte = end;
    }
    return { number: row + 1, fragments };
  });
}
