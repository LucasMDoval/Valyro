import {
  Smartphone,
  Car,
  Watch,
  Gamepad2,
  Laptop,
  Bike,
  Home,
  Shirt,
  Wrench,
  BookOpen,
  BriefcaseBusiness,
  Package,
} from 'lucide-react';

function norm(s: string): string {
  // lower + quita tildes/diacríticos
  return (s || '')
    .toLowerCase()
    .normalize('NFD')
    // eslint-disable-next-line no-control-regex
    .replace(/[\u0300-\u036f]/g, '')
    .trim();
}

function hasAny(haystack: string, needles: string[]): boolean {
  for (const n of needles) {
    if (haystack.includes(n)) return true;
  }
  return false;
}

/**
 * Icono "rápido" para las tarjetas.
 *
 * No depende del backend: intenta inferir la categoría a partir del texto.
 * (Si mañana guardas category_id en BD, puedes cambiar esto para usarlo.)
 */
export function iconForSearchQuery(query: string): JSX.Element {
  const q = norm(query);

  // 🔎 Relojes (marcas + términos)
  if (
    hasAny(q, [
      'reloj',
      'relojes',
      'seiko',
      'rolex',
      'omega',
      'casio',
      'gshock',
      'g-shock',
      'tissot',
      'swatch',
      'citizen',
      'longines',
      'tag heuer',
      'tagheuer',
      'hamilton',
      'breitling',
      'cartier',
      'patek',
      'audemars',
    ])
  ) {
    return <Watch className="w-6 h-6" />;
  }

  // 🚗 Coches
  if (
    hasAny(q, [
      'coche',
      'coches',
      'vehiculo',
      'bmw',
      'audi',
      'mercedes',
      'volkswagen',
      'vw',
      'opel',
      'renault',
      'peugeot',
      'citroen',
      'ford',
      'toyota',
      'hyundai',
      'kia',
      'tesla',
      'nissan',
    ])
  ) {
    return <Car className="w-6 h-6" />;
  }

  // 🎮 Consolas y videojuegos
  if (
    hasAny(q, [
      'ps5',
      'ps4',
      'playstation',
      'xbox',
      'nintendo',
      'switch',
      'wii',
      'steam deck',
      'steamdeck',
      'gameboy',
    ])
  ) {
    return <Gamepad2 className="w-6 h-6" />;
  }

  // 📱 Móviles
  if (
    hasAny(q, [
      'iphone',
      'samsung',
      'xiaomi',
      'redmi',
      'huawei',
      'pixel',
      'movil',
      'telefono',
      'smartphone',
      'android',
    ])
  ) {
    return <Smartphone className="w-6 h-6" />;
  }

  // 💻 Informática
  if (
    hasAny(q, [
      'macbook',
      'portatil',
      'laptop',
      'ordenador',
      'pc',
      'imac',
      'rtx',
      'gtx',
      'gaming',
      'monitor',
      'teclado',
      'raton',
    ])
  ) {
    return <Laptop className="w-6 h-6" />;
  }

  // 🚲 Bicicletas
  if (hasAny(q, ['bici', 'bicicleta', 'bicicletas', 'mtb', 'btt', 'carretera'])) {
    return <Bike className="w-6 h-6" />;
  }

  // 🏠 Hogar
  if (hasAny(q, ['sofa', 'sillon', 'mesa', 'silla', 'cama', 'armario', 'mueble', 'lampara'])) {
    return <Home className="w-6 h-6" />;
  }

  // 👕 Moda
  if (
    hasAny(q, ['zapatilla', 'zapatillas', 'nike', 'adidas', 'ropa', 'camiseta', 'chaqueta', 'pantalon', 'bolso'])
  ) {
    return <Shirt className="w-6 h-6" />;
  }

  // 🧰 Herramientas / motor y accesorios
  if (
    hasAny(q, ['herramienta', 'taladro', 'llave inglesa', 'destornillador', 'recambio', 'neumatico', 'neumaticos'])
  ) {
    return <Wrench className="w-6 h-6" />;
  }

  // 📚 Libros
  if (hasAny(q, ['libro', 'comic', 'comics', 'novela', 'manga'])) {
    return <BookOpen className="w-6 h-6" />;
  }

  // 💼 Empleo
  if (hasAny(q, ['empleo', 'trabajo', 'oferta', 'cv', 'curriculum'])) {
    return <BriefcaseBusiness className="w-6 h-6" />;
  }

  // 📦 Default "genérico"
  return <Package className="w-6 h-6" />;
}
