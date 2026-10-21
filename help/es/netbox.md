---
title: Importar desde NetBox
category: devices
order: 5
summary: Conexión con NetBox, elección de dispositivos, emparejamiento y sincronización.
keywords: netbox importar token api sitio rol etiqueta sincronización dcim
---
Si sus switches están registrados en NetBox, puede traerlos a SwitchMap con sus nombres, direcciones IP y número de puertos. Sección **Búsqueda e importación → NetBox** (solo administradores).

# Conexión {#token}

1. **URL de NetBox**: por ejemplo `https://netbox.company.local`.
2. **Token de API**: créelo en NetBox: perfil de usuario (arriba a la derecha) → **API Tokens** → **Add a token**. Basta con un token de **solo lectura**. Funcionan los dos formatos de token (el clásico y el nuevo `nbt_…`).
3. Si NetBox usa un certificado autofirmado, desmarque **Verificar el certificado del servidor**.
4. Pulse **Comprobar y guardar**.

El token se guarda cifrado en el servidor de SwitchMap y nunca se envía al navegador.

# Importación {#import}

1. Elija los filtros: **sitio**, **rol** (por ejemplo «Access switch»), **etiqueta**. **Solo con estado «Active»** oculta los equipos retirados y planificados.
2. Pulse **Mostrar dispositivos**.
3. Marque los que necesite (por defecto se marcan los nuevos con IP) y pulse **Importar seleccionados**.

La dirección IP se toma de la **Primary IP** del dispositivo y el número de puertos de sus interfaces físicas. Indique la configuración SNMP en la misma página: se aplica a todos los switches importados.

# Emparejamiento {#matching}

Un dispositivo de NetBox se considera ya añadido si coincide:

1. el vínculo (el switch ya se importó antes desde NetBox);
2. o la dirección IP;
3. o el nombre.

Para estos dispositivos se muestra qué cambiará. **En los ya añadidos, actualizar nombre e IP desde NetBox** activa la actualización. El mapa de puertos, las conexiones y el historial no cambian.

# Sincronización {#sync}

El bloque **Switches vinculados**: **Sincronizar ahora** actualiza desde NetBox los nombres e IP de todos los switches vinculados. **Automáticamente cada hora** lo hace de forma programada. Los dispositivos nuevos no se añaden automáticamente: solo mediante importación.

La página de un switch vinculado tiene un enlace **NetBox** a su ficha en NetBox.
